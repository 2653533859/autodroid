// Canvas renderers cannot resolve CSS variables; keep this palette in sync with main.css.
export const chartColors = Object.freeze({
  primary: '#466b98', success: '#39725a', warning: '#936323', danger: '#ad4f4a',
  muted: '#677381', text: '#202731', border: '#e5e9ee', purple: '#796797',
})
export const chartTheme = {
  color: [chartColors.primary, chartColors.success, chartColors.warning, chartColors.danger, chartColors.purple, chartColors.muted],
  backgroundColor: 'transparent',
  textStyle: { color: chartColors.text, fontFamily: '-apple-system, PingFang SC, sans-serif', fontSize: 12 },
  title: { textStyle: { color: chartColors.text, fontSize: 14, fontWeight: 500 }, subtextStyle: { color: chartColors.muted } },
  legend: { textStyle: { color: chartColors.muted, fontSize: 12 }, icon: 'roundRect', itemWidth: 12, itemHeight: 3 },
  tooltip: { backgroundColor: '#ffffff', borderColor: chartColors.border, textStyle: { color: chartColors.text, fontSize: 12 }, extraCssText: 'box-shadow:0 4px 16px rgba(32,39,49,.08);border-radius:6px;' },
  categoryAxis: { axisLine: { lineStyle: { color: chartColors.border } }, axisTick: { show: false }, axisLabel: { color: chartColors.muted }, splitLine: { show: false } },
  valueAxis: { axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: chartColors.muted }, splitLine: { lineStyle: { color: chartColors.border } } },
  line: { symbolSize: 5, lineStyle: { width: 2 } },
}
