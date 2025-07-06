"use client"

import * as React from "react"
import { 
  Cpu, 
  HardDrive, 
  Wifi, 
  Database,
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock
} from "lucide-react"

interface SystemMetric {
  name: string
  value: number
  unit: string
  status: "healthy" | "warning" | "critical"
  icon: React.ElementType
}

interface SystemHealthProps {
  refreshInterval?: number
}

export default function SystemHealth({ refreshInterval = 30000 }: SystemHealthProps) {
  const [metrics, setMetrics] = React.useState<SystemMetric[]>([
    { name: "CPU Usage", value: 45, unit: "%", status: "healthy", icon: Cpu },
    { name: "Memory Usage", value: 68, unit: "%", status: "warning", icon: HardDrive },
    { name: "Network", value: 99.8, unit: "%", status: "healthy", icon: Wifi },
    { name: "Database", value: 12, unit: "ms", status: "healthy", icon: Database },
  ])

  const [lastUpdate, setLastUpdate] = React.useState(new Date())

  // Simulate real-time updates
  React.useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(prev => prev.map(metric => ({
        ...metric,
        value: metric.name === "Database" 
          ? Math.random() * 50 + 5 // 5-55ms
          : Math.random() * 100 // 0-100%
      })))
      setLastUpdate(new Date())
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [refreshInterval])

  const getStatusColor = (status: string) => {
    switch (status) {
      case "healthy": return "text-green-600 bg-green-100"
      case "warning": return "text-yellow-600 bg-yellow-100"
      case "critical": return "text-red-600 bg-red-100"
      default: return "text-gray-600 bg-gray-100"
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy": return CheckCircle
      case "warning": return AlertTriangle
      case "critical": return AlertTriangle
      default: return Clock
    }
  }

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">System Health</h3>
            <p className="text-sm text-gray-500">Real-time system performance metrics</p>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-xs text-gray-500">
              Updated {lastUpdate.toLocaleTimeString('nl-NL')}
            </span>
          </div>
        </div>
      </div>

      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {metrics.map((metric) => {
            const StatusIcon = getStatusIcon(metric.status)
            
            return (
              <div key={metric.name} className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <metric.icon className="h-4 w-4 text-gray-600" />
                    <span className="text-sm font-medium text-gray-900">{metric.name}</span>
                  </div>
                  <div className={`p-1 rounded-full ${getStatusColor(metric.status)}`}>
                    <StatusIcon className="h-3 w-3" />
                  </div>
                </div>
                
                <div className="flex items-end space-x-2">
                  <span className="text-2xl font-bold text-gray-900">
                    {metric.name === "Database" ? metric.value.toFixed(1) : Math.round(metric.value)}
                  </span>
                  <span className="text-sm text-gray-500 pb-1">{metric.unit}</span>
                </div>
                
                {/* Progress bar for percentage metrics */}
                {metric.unit === "%" && (
                  <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full transition-all duration-500 ${
                        metric.status === "healthy" ? "bg-green-500" :
                        metric.status === "warning" ? "bg-yellow-500" : "bg-red-500"
                      }`}
                      style={{ width: `${metric.value}%` }}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Overall System Status */}
        <div className="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
          <div className="flex items-center space-x-2">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <div>
              <p className="text-sm font-medium text-green-800">System Operating Normally</p>
              <p className="text-xs text-green-600">All critical services are running smoothly</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 