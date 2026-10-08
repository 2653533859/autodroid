<script setup>
import { chartColors, chartTheme } from '@/utils/chartTheme'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import './echartsSetup'
import {
    buildClockSeries,
    clockTimeToTimestamp,
    findClosestSeriesPoint,
    formatAxisTime,
    resolveReportBaseDate,
} from './reportFormatters'

const props = defineProps({
    perfData: { type: Array, default: () => [] },
    crashEvents: { type: Array, default: () => [] },
    startedAt: { type: String, default: '' },
    chartGroup: { type: String, default: '' },
})

const emit = defineEmits(['mark-point-click'])

const reportBaseDate = computed(() => resolveReportBaseDate(props.startedAt))

const chartOption = computed(() => {
    const cpuSeries = buildClockSeries(reportBaseDate.value, props.perfData, 'cpu')
    const memSeries = buildClockSeries(reportBaseDate.value, props.perfData, 'mem')

    const crashMarkPoints = props.crashEvents
        .map((event) => {
            const eventTimestamp = clockTimeToTimestamp(reportBaseDate.value, event.time)
            const perfPoint = findClosestSeriesPoint(cpuSeries, eventTimestamp)
            if (eventTimestamp === null || !perfPoint) return null
            return {
                coord: [eventTimestamp, perfPoint[1]],
                itemStyle: { color: event.type === 'ANR' ? chartColors.warning : chartColors.danger },
                symbol: 'pin',
                symbolSize: 40,
                value: event.type,
                _eventData: event,
            }
        })
        .filter(Boolean)

    return {
        title: { text: '性能监控', left: 'center', textStyle: { fontSize: 14, color: chartColors.text } },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
        },
        legend: { data: ['CPU (%)', '内存 (MB)'], top: 35 },
        toolbox: {
            right: 20,
            feature: { saveAsImage: {} },
        },
        grid: { left: 60, right: 60, top: 80, bottom: 60 },
        dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 10 }],
        xAxis: {
            type: 'time',
            boundaryGap: false,
            axisLabel: {
                formatter: (value) => formatAxisTime(value),
            },
        },
        yAxis: [
            {
                type: 'value',
                name: 'CPU (%)',
                position: 'left',
                axisLabel: { formatter: '{value}%' },
                min: 0,
            },
            {
                type: 'value',
                name: '内存 (MB)',
                position: 'right',
                axisLabel: { formatter: '{value} MB' },
                min: 0,
            },
        ],
        series: [
            {
                name: 'CPU (%)',
                type: 'line',
                smooth: true,
                data: cpuSeries,
                yAxisIndex: 0,
                lineStyle: { color: chartColors.primary, width: 2 },
                itemStyle: { color: chartColors.primary },
                areaStyle: { color: chartColors.primary, opacity: 0.08 },
                markPoint: {
                    data: crashMarkPoints,
                    label: {
                        show: true,
                        formatter: (p) => p.data.value === 'ANR' ? 'ANR' : 'Crash',
                        color: '#fff',
                        fontSize: 12,
                    },
                },
            },
            {
                name: '内存 (MB)',
                type: 'line',
                smooth: true,
                data: memSeries,
                yAxisIndex: 1,
                lineStyle: { color: chartColors.success, width: 2 },
                itemStyle: { color: chartColors.success },
                areaStyle: { color: chartColors.success, opacity: 0.08 },
            },
        ],
    }
})

const handleChartClick = (params) => {
    if (params.componentType === 'markPoint' && params.data?._eventData) {
        emit('mark-point-click', params.data._eventData)
    }
}
</script>

<template>
    <el-card shadow="never" class="chart-card">
        <VChart v-if="perfData.length" :theme="chartTheme"
            :option="chartOption"
            :group="chartGroup"
            autoresize
            style="height: 400px; width: 100%"
            @click="handleChartClick"
        />
        <el-empty v-if="!perfData.length" description="本次执行未采集到监控数据" :image-size="56" />
    </el-card>
</template>

<style scoped>
.chart-card {
    border-radius: var(--ad-radius);
}

@media (max-width: 767px) {
  :deep(.el-button), :deep(.el-radio-button__inner), :deep(.el-select__wrapper), :deep(.el-collapse-item__header) { min-height: 44px; }
  :deep(.el-input__inner), :deep(.el-textarea__inner) { font-size: 16px; }
  :deep(.el-form-item__label), :deep(.el-table), :deep(.el-descriptions), :deep(.el-tabs__item), :deep(.el-collapse-item__content) { font-size: 14px; }
  :deep(.el-table__cell) { font-size: 14px; }
}
</style>
