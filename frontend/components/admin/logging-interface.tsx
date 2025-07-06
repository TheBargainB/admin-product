"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { AlertCircle, CheckCircle, Clock, Filter, Download, RefreshCw, Search } from 'lucide-react'

interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'critical'
  message: string
  component: string
  store?: string
  jobId?: string
}

interface JobHistoryEntry {
  id: string
  store: string
  type: string
  status: 'success' | 'failure' | 'cancelled' | 'running'
  startTime: string
  endTime?: string
  duration?: number
  productsProcessed: number
  errors: number
}

export default function LoggingInterface() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [jobHistory, setJobHistory] = useState<JobHistoryEntry[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    loadMockData()
  }, [])

  const loadMockData = () => {
    const mockLogs: LogEntry[] = [
      {
        id: '1',
        timestamp: new Date(Date.now() - 300000).toISOString(),
        level: 'info',
        message: 'Albert Heijn scraping completed successfully',
        component: 'scraper',
        store: 'albert_heijn',
        jobId: 'job_001'
      },
      {
        id: '2',
        timestamp: new Date(Date.now() - 900000).toISOString(),
        level: 'warning',
        message: 'Rate limit encountered, retrying in 30s',
        component: 'scraper',
        store: 'jumbo'
      },
      {
        id: '3',
        timestamp: new Date(Date.now() - 1800000).toISOString(),
        level: 'error',
        message: 'Database connection timeout',
        component: 'database'
      }
    ]

    const mockJobHistory: JobHistoryEntry[] = [
      {
        id: 'job_001',
        store: 'albert_heijn',
        type: 'full_scrape',
        status: 'success',
        startTime: new Date(Date.now() - 3000000).toISOString(),
        endTime: new Date(Date.now() - 300000).toISOString(),
        duration: 45.2,
        productsProcessed: 1250,
        errors: 0
      },
      {
        id: 'job_002',
        store: 'jumbo',
        type: 'price_update',
        status: 'running',
        startTime: new Date(Date.now() - 1200000).toISOString(),
        productsProcessed: 850,
        errors: 1
      }
    ]

    setLogs(mockLogs)
    setJobHistory(mockJobHistory)
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'error':
      case 'critical':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />
      default:
        return <CheckCircle className="h-4 w-4 text-blue-500" />
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failure':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'running':
        return <Clock className="h-4 w-4 text-blue-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-500" />
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">System Logs & Monitoring</h2>
          <p className="text-muted-foreground">
            Monitor system activities and job history
          </p>
        </div>
        
        <Button variant="outline" onClick={loadMockData} disabled={isLoading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      <Tabs defaultValue="logs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="logs">System Logs</TabsTrigger>
          <TabsTrigger value="jobs">Job History</TabsTrigger>
        </TabsList>

        <TabsContent value="logs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Logs ({logs.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-96">
                <div className="space-y-2">
                  {logs.map((log) => (
                    <div key={log.id} className="flex items-start gap-3 p-3 rounded-lg border">
                      {getLevelIcon(log.level)}
                      
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={log.level === 'error' ? 'destructive' : 'secondary'}>
                            {log.level.toUpperCase()}
                          </Badge>
                          <Badge variant="outline">{log.component}</Badge>
                          {log.store && <Badge variant="outline">{log.store}</Badge>}
                          <span className="text-sm text-muted-foreground ml-auto">
                            {formatTimestamp(log.timestamp)}
                          </span>
                        </div>
                        <p className="text-sm">{log.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="jobs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Job History</CardTitle>
              <CardDescription>Track all scraping jobs and execution details</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {jobHistory.map((job) => (
                  <div key={job.id} className="flex items-center justify-between p-4 rounded-lg border">
                    <div className="flex items-center gap-4">
                      {getStatusIcon(job.status)}
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium">{job.store.toUpperCase()}</span>
                          <Badge variant="outline">{job.type}</Badge>
                          <Badge variant={job.status === 'success' ? 'default' : 'destructive'}>
                            {job.status.toUpperCase()}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Started: {formatTimestamp(job.startTime)}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium">{job.productsProcessed} products</div>
                      <div className="text-sm text-muted-foreground">{job.errors} errors</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
} 