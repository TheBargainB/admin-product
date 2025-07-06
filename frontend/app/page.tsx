import { Metadata } from 'next'
import DashboardLayout from '@/components/layout/dashboard-layout'
import DashboardOverview from '@/components/dashboard/dashboard-overview'

export const metadata: Metadata = {
  title: 'Dashboard - BargainB Admin',
  description: 'Overview of grocery price scraping operations and system health',
}

export default function DashboardPage() {
  return (
    <DashboardLayout>
      <div className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
          <div className="flex items-center space-x-2">
            <span className="text-sm text-muted-foreground">
              Last updated: {new Date().toLocaleTimeString('nl-NL')}
            </span>
          </div>
        </div>
        <DashboardOverview />
      </div>
    </DashboardLayout>
  )
} 