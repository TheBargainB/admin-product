"use client"

import * as React from "react"
import { 
  Play, 
  Pause, 
  Square, 
  Clock, 
  CheckCircle, 
  AlertCircle,
  RotateCcw,
  TrendingUp,
  Calendar,
  Timer
} from "lucide-react"
import { getRecentJobs, getJobStatistics } from "@/lib/api"

interface ScrapingJob {
  id: string
  store: string
  type: "full_scrape" | "price_update" | "validation"
  status: "pending" | "running" | "completed" | "failed" | "paused"
  progress: number
  startTime: string
  estimatedEnd?: string
  productsProcessed: number
  productsTotal: number
  errorCount: number
}

interface JobStatistics {
  jobsToday: number
  successRate: number
  avgDuration: number
}

interface JobMonitorProps {
  refreshInterval?: number
}

export default function JobMonitor({ refreshInterval = 5000 }: JobMonitorProps) {
  const [jobs, setJobs] = React.useState<ScrapingJob[]>([])
  const [stats, setStats] = React.useState<JobStatistics>({
    jobsToday: 0,
    successRate: 0,
    avgDuration: 0
  })
  const [loading, setLoading] = React.useState(true)

  const fetchJobData = React.useCallback(async () => {
    try {
      const response = await getRecentJobs()
      
      // Handle new edge function response structure
      if (response && typeof response === 'object' && response.jobs && response.statistics) {
        setJobs(response.jobs)
        setStats(response.statistics)
      } else if (Array.isArray(response)) {
        // Fallback for old structure
        setJobs(response)
        setStats({ jobsToday: 0, successRate: 0, avgDuration: 0 })
      } else {
        setJobs([])
        setStats({ jobsToday: 0, successRate: 0, avgDuration: 0 })
      }
    } catch (error) {
      console.error('Error fetching job data:', error)
      setJobs([])
      setStats({ jobsToday: 0, successRate: 0, avgDuration: 0 })
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    fetchJobData()
    
    // Refresh data at specified interval
    const interval = setInterval(fetchJobData, refreshInterval)
    return () => clearInterval(interval)
  }, [fetchJobData, refreshInterval])

  const getStatusConfig = (status: string) => {
    switch (status) {
      case "running":
        return { color: "text-blue-600", bg: "bg-blue-100", icon: Play }
      case "completed":
        return { color: "text-green-600", bg: "bg-green-100", icon: CheckCircle }
      case "failed":
        return { color: "text-red-600", bg: "bg-red-100", icon: AlertCircle }
      case "paused":
        return { color: "text-yellow-600", bg: "bg-yellow-100", icon: Pause }
      case "pending":
        return { color: "text-gray-600", bg: "bg-gray-100", icon: Clock }
      default:
        return { color: "text-gray-600", bg: "bg-gray-100", icon: Square }
    }
  }

  const getJobTypeLabel = (type: string) => {
    switch (type) {
      case "full_scrape": return "Full Scrape"
      case "price_update": return "Price Update"
      case "validation": return "Validation"
      default: return type
    }
  }

  const formatDuration = (startTime: string, endTime?: string) => {
    const start = new Date(startTime)
    const end = endTime ? new Date(endTime) : new Date()
    const diff = end.getTime() - start.getTime()
    const minutes = Math.floor(diff / 60000)
    const seconds = Math.floor((diff % 60000) / 1000)
    return `${minutes}m ${seconds}s`
  }

  const handleJobAction = (jobId: string, action: "pause" | "resume" | "stop" | "retry") => {
    // For now, just update local state - in a real app, this would call the backend API
    setJobs(prev => prev.map(job => {
      if (job.id === jobId) {
        switch (action) {
          case "pause":
            return { ...job, status: "paused" as const }
          case "resume":
            return { ...job, status: "running" as const }
          case "stop":
            return { ...job, status: "failed" as const }
          case "retry":
            return { ...job, status: "pending" as const, progress: 0, productsProcessed: 0, errorCount: 0 }
          default:
            return job
        }
      }
      return job
    }))
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Job Monitor</h3>
              <p className="text-sm text-gray-500">Real-time scraping job status and progress</p>
            </div>
          </div>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-20 bg-gray-200 rounded-lg"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Job Monitor</h3>
            <p className="text-sm text-gray-500">Real-time scraping job status and progress</p>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-500">
              {jobs.filter(j => j.status === "running").length} active jobs
            </span>
          </div>
        </div>
      </div>

      <div className="p-6">
        <div className="space-y-4">
          {jobs.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500">No recent jobs</p>
            </div>
          ) : (
            jobs.map((job) => {
              const statusConfig = getStatusConfig(job.status)
              const StatusIcon = statusConfig.icon
              
              return (
                <div key={job.id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <div className={`p-2 rounded-full ${statusConfig.bg}`}>
                        <StatusIcon className={`h-4 w-4 ${statusConfig.color}`} />
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-900">{job.store}</h4>
                        <p className="text-sm text-gray-500">{getJobTypeLabel(job.type)}</p>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      {job.status === "running" && (
                        <>
                          <button
                            onClick={() => handleJobAction(job.id, "pause")}
                            className="p-1 text-gray-400 hover:text-yellow-600"
                            title="Pause job"
                          >
                            <Pause className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleJobAction(job.id, "stop")}
                            className="p-1 text-gray-400 hover:text-red-600"
                            title="Stop job"
                          >
                            <Square className="h-4 w-4" />
                          </button>
                        </>
                      )}
                      {job.status === "paused" && (
                        <button
                          onClick={() => handleJobAction(job.id, "resume")}
                          className="p-1 text-gray-400 hover:text-blue-600"
                          title="Resume job"
                        >
                          <Play className="h-4 w-4" />
                        </button>
                      )}
                      {job.status === "failed" && (
                        <button
                          onClick={() => handleJobAction(job.id, "retry")}
                          className="p-1 text-gray-400 hover:text-green-600"
                          title="Retry job"
                        >
                          <RotateCcw className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Progress bar */}
                  {job.status === "running" && (
                    <div className="mb-4">
                      <div className="flex items-center justify-between text-sm text-gray-600 mb-1">
                        <span>Progress</span>
                        <span>{Math.round(job.progress)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Job details */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-gray-500">Products</p>
                      <p className="font-medium text-gray-900">
                        {job.productsProcessed.toLocaleString()} / {job.productsTotal.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Duration</p>
                      <p className="font-medium text-gray-900">
                        {formatDuration(job.startTime)}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Errors</p>
                      <p className={`font-medium ${job.errorCount > 0 ? "text-red-600" : "text-gray-900"}`}>
                        {job.errorCount}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-500">Started</p>
                      <p className="font-medium text-gray-900">
                        {new Date(job.startTime).toLocaleTimeString('nl-NL')}
                      </p>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-5 w-5 text-blue-600" />
              <div>
                <p className="text-sm font-medium text-blue-800">Jobs Today</p>
                <p className="text-lg font-bold text-blue-900">{stats.jobsToday}</p>
              </div>
            </div>
          </div>
          <div className="bg-green-50 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              <div>
                <p className="text-sm font-medium text-green-800">Success Rate</p>
                <p className="text-lg font-bold text-green-900">{stats.successRate}%</p>
              </div>
            </div>
          </div>
          <div className="bg-purple-50 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <Timer className="h-5 w-5 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-purple-800">Avg Duration</p>
                <p className="text-lg font-bold text-purple-900">{stats.avgDuration}m</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 