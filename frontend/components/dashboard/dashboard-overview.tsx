"use client"

import * as React from "react"
import { 
  Activity, 
  ShoppingCart, 
  Database, 
  CheckCircle,
  AlertCircle,
  Clock,
  Zap
} from "lucide-react"
import SystemHealth from "./system-health"
import JobMonitor from "./job-monitor"
import MetricsChart from "./metrics-chart"
import { getDashboardMetrics, getStoreData, getStoreChartData } from "@/lib/api"

interface DashboardMetrics {
  totalProducts: number
  activeStores: number
  todayUpdates: number
  systemHealth: number
}

interface StoreData {
  name: string
  status: string
  lastScrape: string
  products: number
}

interface ChartData {
  label: string
  value: number
  change: number
}

export default function DashboardOverview() {
  const [timeRange, setTimeRange] = React.useState<"24h" | "7d" | "30d">("24h")
  const [metrics, setMetrics] = React.useState<DashboardMetrics>({
    totalProducts: 0,
    activeStores: 0,
    todayUpdates: 0,
    systemHealth: 0
  })
  const [stores, setStores] = React.useState<StoreData[]>([])
  const [chartData, setChartData] = React.useState<ChartData[]>([])
  const [loading, setLoading] = React.useState(true)

  const fetchDashboardData = React.useCallback(async () => {
    try {
      setLoading(true)
      
      // Fetch all data in parallel
      const [metricsData, storesData, chartDataResult] = await Promise.all([
        getDashboardMetrics(),
        getStoreData(), 
        getStoreChartData()
      ])

      setMetrics(metricsData)
      setStores(storesData)
      setChartData(chartDataResult)
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    fetchDashboardData()
    
    // Refresh data every 30 seconds
    const interval = setInterval(fetchDashboardData, 30000)
    return () => clearInterval(interval)
  }, [fetchDashboardData])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-white rounded-lg shadow p-6 border border-gray-200 animate-pulse">
              <div className="flex items-center justify-between">
                <div>
                  <div className="h-4 bg-gray-200 rounded w-24 mb-2"></div>
                  <div className="h-8 bg-gray-200 rounded w-16"></div>
                </div>
                <div className="w-12 h-12 bg-gray-200 rounded-full"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Products</p>
              <p className="text-2xl font-bold text-gray-900">{metrics.totalProducts.toLocaleString()}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-full">
              <ShoppingCart className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Active Stores</p>
              <p className="text-2xl font-bold text-gray-900">{metrics.activeStores}</p>
            </div>
            <div className="p-3 bg-green-100 rounded-full">
              <Database className="h-6 w-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Today Updates</p>
              <p className="text-2xl font-bold text-gray-900">{metrics.todayUpdates.toLocaleString()}</p>
            </div>
            <div className="p-3 bg-orange-100 rounded-full">
              <Activity className="h-6 w-6 text-orange-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">System Health</p>
              <p className="text-2xl font-bold text-gray-900">{metrics.systemHealth}%</p>
            </div>
            <div className="p-3 bg-purple-100 rounded-full">
              <Zap className="h-6 w-6 text-purple-600" />
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Store Status</h3>
          <p className="text-sm text-gray-500">Real-time scraping status for all stores</p>
        </div>
        <div className="p-6 space-y-4">
          {stores.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500">No stores available</p>
            </div>
          ) : (
            stores.map((store) => (
              <div key={store.name} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-full ${
                    store.status === "active" ? "bg-green-100" :
                    store.status === "idle" ? "bg-yellow-100" : "bg-red-100"
                  }`}>
                    {store.status === "active" && <CheckCircle className="h-4 w-4 text-green-600" />}
                    {store.status === "idle" && <Clock className="h-4 w-4 text-yellow-600" />}
                    {store.status === "error" && <AlertCircle className="h-4 w-4 text-red-600" />}
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900">{store.name}</h4>
                    <p className="text-sm text-gray-500">Last scrape: {store.lastScrape}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-medium text-gray-900">{store.products.toLocaleString()}</p>
                  <p className="text-sm text-gray-500">products</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Advanced Dashboard Components */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SystemHealth />
        <JobMonitor />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MetricsChart
          title="Store Performance"
          type="bar"
          data={chartData}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
        />
        <MetricsChart
          title="Price Trends"
          type="line"
          data={chartData}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
        />
      </div>
    </div>
  )
} 