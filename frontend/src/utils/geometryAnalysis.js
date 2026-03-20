import { readSelectedAnalysisScope } from "./analysisScope";

function monthFromDate(dateString) {
  const value = String(dateString || "").slice(0, 10);
  const [, month] = value.split("-");
  return Number(month || 0);
}

function yearFromDate(dateString) {
  return String(dateString || "").slice(0, 4);
}

function groupByMonth(rows, seedFactory, consumeRow, finalizeRow) {
  const grouped = new Map();
  rows.forEach((row) => {
    const month = monthFromDate(row.date);
    if (!month) {
      return;
    }
    if (!grouped.has(month)) {
      grouped.set(month, seedFactory());
    }
    consumeRow(grouped.get(month), row);
  });
  return Array.from(grouped.entries())
    .sort((left, right) => left[0] - right[0])
    .map(([month, payload]) => finalizeRow(month, payload));
}

export function readGeometryScope() {
  const scope = readSelectedAnalysisScope();
  return scope?.mode === "geometry" && scope.geometry ? scope : null;
}

export function buildRainfallMonthly(rows) {
  return groupByMonth(
    rows,
    () => ({ values: [] }),
    (group, row) => {
      group.values.push(Number(row.rainfall_mm || 0));
    },
    (month, group) => ({
      month,
      total: group.values.reduce((sum, value) => sum + value, 0).toFixed(2),
      average: (group.values.reduce((sum, value) => sum + value, 0) / (group.values.length || 1)).toFixed(2),
      max: Math.max(...group.values, 0).toFixed(2),
      days: group.values.length,
    })
  );
}

export function buildTemperatureMonthly(rows) {
  return groupByMonth(
    rows,
    () => ({ mean: [], min: [], max: [] }),
    (group, row) => {
      group.mean.push(Number(row.temp_mean || 0));
      group.min.push(Number(row.temp_min || 0));
      group.max.push(Number(row.temp_max || 0));
    },
    (month, group) => ({
      month,
      avg_temp: (group.mean.reduce((sum, value) => sum + value, 0) / (group.mean.length || 1)).toFixed(2),
      avg_min: (group.min.reduce((sum, value) => sum + value, 0) / (group.min.length || 1)).toFixed(2),
      avg_max: (group.max.reduce((sum, value) => sum + value, 0) / (group.max.length || 1)).toFixed(2),
      min_temp: (group.min.length ? Math.min(...group.min) : 0).toFixed(2),
      max_temp: (group.max.length ? Math.max(...group.max) : 0).toFixed(2),
    })
  );
}

export function buildNdviMonthly(rows) {
  return groupByMonth(
    rows,
    () => ({ mean: [], min: [], max: [], vegetation: [] }),
    (group, row) => {
      group.mean.push(Number(row.ndvi_mean || 0));
      group.min.push(Number(row.ndvi_min || 0));
      group.max.push(Number(row.ndvi_max || 0));
      group.vegetation.push(Number(row.vegetation_area_pct || 0));
    },
    (month, group) => ({
      month,
      avg_ndvi: (group.mean.reduce((sum, value) => sum + value, 0) / (group.mean.length || 1)).toFixed(4),
      min_ndvi: (group.min.length ? Math.min(...group.min) : 0).toFixed(4),
      max_ndvi: (group.max.length ? Math.max(...group.max) : 0).toFixed(4),
      avg_vegetation_pct: (group.vegetation.reduce((sum, value) => sum + value, 0) / (group.vegetation.length || 1)).toFixed(2),
    })
  );
}

export function buildTvdiMonthly(rows) {
  return groupByMonth(
    rows,
    () => ({ mean: [], min: [], max: [], lst: [], drought: [], severeDays: 0 }),
    (group, row) => {
      group.mean.push(Number(row.tvdi_mean || 0));
      group.min.push(Number(row.tvdi_min || 0));
      group.max.push(Number(row.tvdi_max || 0));
      group.lst.push(Number(row.lst_mean || 0));
      group.drought.push(Number(row.drought_area_pct || 0));
      if (row.drought_class === "severe" || row.drought_class === "extreme") {
        group.severeDays += 1;
      }
    },
    (month, group) => ({
      month,
      avg_tvdi: (group.mean.reduce((sum, value) => sum + value, 0) / (group.mean.length || 1)).toFixed(4),
      min_tvdi: (group.min.length ? Math.min(...group.min) : 0).toFixed(4),
      max_tvdi: (group.max.length ? Math.max(...group.max) : 0).toFixed(4),
      avg_lst: (group.lst.reduce((sum, value) => sum + value, 0) / (group.lst.length || 1)).toFixed(2),
      avg_drought_pct: (group.drought.reduce((sum, value) => sum + value, 0) / (group.drought.length || 1)).toFixed(2),
      severe_days: group.severeDays,
    })
  );
}

export function buildTvdiSevereEvents(rows) {
  return rows
    .filter((row) => row.drought_class === "severe" || row.drought_class === "extreme")
    .map((row) => ({
      date: row.date,
      tvdi: Number(row.tvdi_mean || 0).toFixed(4),
      lst: Number(row.lst_mean || 0).toFixed(2),
      drought_pct: Number(row.drought_area_pct || 0).toFixed(2),
      classification: row.drought_class,
    }));
}

export function buildTvdiDroughtSummary(rows) {
  return rows.reduce((accumulator, row) => {
    const year = yearFromDate(row.date);
    const classification = row.drought_class || "unknown";
    if (!accumulator[year]) {
      accumulator[year] = {};
    }
    if (!accumulator[year][classification]) {
      accumulator[year][classification] = { count: 0, avg_tvdi_total: 0 };
    }
    accumulator[year][classification].count += 1;
    accumulator[year][classification].avg_tvdi_total += Number(row.tvdi_mean || 0);
    return accumulator;
  }, {});
}

export function finalizeTvdiDroughtSummary(summary) {
  return Object.fromEntries(
    Object.entries(summary).map(([year, classes]) => [
      year,
      Object.fromEntries(
        Object.entries(classes).map(([classification, payload]) => [
          classification,
          {
            count: payload.count,
            avg_tvdi: (payload.avg_tvdi_total / (payload.count || 1)).toFixed(4),
          },
        ])
      ),
    ])
  );
}
