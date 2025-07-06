"use client"

import * as React from "react"
import { 
  TrendingUp, 
  TrendingDown, 
  BarChart3, 
  PieChart, 
  Calendar,
  Download
} from "lucide-react"

interface ChartData {
  label: string
  value: number
  change?: number
}

interface MetricsChartProps {
  title: string
  type: "line" | "bar" | "pie"
  data: ChartData[]
  timeRange: "24h" | "7d" | "30d"
  onTimeRangeChange?: (range: "24h" | "7d" | "30d") => void
}

export default function MetricsChart({ 
  title, 
  type, 
  data, 
  timeRange, 
  onTimeRangeChange 
}: MetricsChartProps) {
  const [selectedMetric, setSelectedMetric] = React.useState<string | null>(null)

  // Mock chart data for demonstration
  const chartData = React.useMemo(() => {
    const baseData = Array.from({ length: 24 }, (_, i) => ({
      time: `${i}:00`,
      value: Math.floor(Math.random() * 100) + 50,
      products: Math.floor(Math.random() * 1000) + 500,
      errors: Math.floor(Math.random() * 10)
    }))
    return baseData
  }, [timeRange])

  const totalValue = data.reduce((sum, item) => sum + item.value, 0)
  const avgChange = data.reduce((sum, item) => sum + (item.change || 0), 0) / data.length

  const getTimeRangeLabel = (range: string) => {
    switch (range) {
      case "24h": return "Last 24 Hours"
      case "7d": return "Last 7 Days"
      case "30d": return "Last 30 Days"
      default: return range
    }
  }

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            <p className="text-sm text-gray-500">
              {getTimeRangeLabel(timeRange)} • {totalValue.toLocaleString()} total
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1 bg-gray-100 rounded-lg p-1">
              {(["24h", "7d", "30d"] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => onTimeRangeChange?.(range)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    timeRange === range
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>
            <button className="p-2 text-gray-400 hover:text-gray-600">
              <Download className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* Chart Area - Simplified representation */}
        <div className="mb-6">
          {type === "line" && (
            <div className="h-64 bg-gray-50 rounded-lg flex items-end justify-between p-4">
              {chartData.slice(0, 12).map((point, index) => (
                <div key={index} className="flex flex-col items-center space-y-1">
                  <div
                    className="w-2 bg-blue-500 rounded-t"
                    style={{ height: `${(point.value / 150) * 100}%` }}
                  />
                  <span className="text-xs text-gray-500">{point.time}</span>
                </div>
              ))}
            </div>
          )}

          {type === "bar" && (
            <div className="h-64 bg-gray-50 rounded-lg flex items-end justify-between p-4">
              {data.map((item, index) => (
                <div key={index} className="flex flex-col items-center space-y-2">
                  <div
                    className="w-8 bg-gradient-to-t from-blue-500 to-blue-300 rounded-t"
                    style={{ height: `${(item.value / Math.max(...data.map(d => d.value))) * 180}px` }}
                  />
                  <span className="text-xs text-gray-500 text-center">{item.label}</span>
                </div>
              ))}
            </div>
          )}

          {type === "pie" && (
            <div className="h-64 flex items-center justify-center">
              <div className="relative w-48 h-48">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  {data.map((item, index) => {
                    const percentage = (item.value / totalValue) * 100
                    const strokeDasharray = `${percentage} ${100 - percentage}`
                    const colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
                    
                    return (
                      <circle
                        key={index}
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke={colors[index % colors.length]}
                        strokeWidth="8"
                        strokeDasharray={strokeDasharray}
                        strokeDashoffset={-data.slice(0, index).reduce((sum, d) => sum + (d.value / totalValue) * 100, 0)}
                        className="transition-all duration-300"
                      />
                    )
                  })}
                </svg>
              </div>
            </div>
          )}
        </div>

        {/* Data Legend */}
        <div className="space-y-3">
          {data.map((item, index) => (
            <div
              key={index}
              className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                selectedMetric === item.label ? "bg-blue-50 border border-blue-200" : "bg-gray-50 hover:bg-gray-100"
              }`}
              onClick={() => setSelectedMetric(selectedMetric === item.label ? null : item.label)}
            >
              <div className="flex items-center space-x-3">
                <div className={`w-3 h-3 rounded-full ${
                  index === 0 ? "bg-blue-500" :
                  index === 1 ? "bg-green-500" :
                  index === 2 ? "bg-yellow-500" :
                  index === 3 ? "bg-red-500" : "bg-purple-500"
                }`} />
                <span className="font-medium text-gray-900">{item.label}</span>
              </div>
              <div className="flex items-center space-x-4">
                <span className="text-lg font-bold text-gray-900">{item.value.toLocaleString()}</span>
                {item.change !== undefined && (
                  <div className={`flex items-center space-x-1 ${
                    item.change > 0 ? "text-green-600" : "text-red-600"
                  }`}>
                    {item.change > 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                    <span className="text-sm font-medium">{Math.abs(item.change)}%</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Summary Stats */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-blue-600">Average</p>
            <p className="text-xl font-bold text-blue-900">{Math.round(totalValue / data.length).toLocaleString()}</p>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <p className="text-sm text-green-600">Trend</p>
            <p className={`text-xl font-bold ${avgChange > 0 ? "text-green-900" : "text-red-900"}`}>
              {avgChange > 0 ? "+" : ""}{avgChange.toFixed(1)}%
            </p>
          </div>
          <div className="text-center p-4 bg-purple-50 rounded-lg">
            <p className="text-sm text-purple-600">Peak</p>
            <p className="text-xl font-bold text-purple-900">{Math.max(...data.map(d => d.value)).toLocaleString()}</p>
          </div>
        </div>
      </div>
    </div>
  )
} 