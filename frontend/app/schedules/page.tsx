"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { Trash2, Edit, Play, Clock, Calendar, Settings } from "lucide-react";
import DashboardLayout from "@/components/layout/dashboard-layout";

// Backend configuration
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// Types
interface Store {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
}

interface Schedule {
  id: string;
  store_id: string;
  schedule_type: string;
  cron_expression: string;
  timezone: string;
  is_active: boolean;
  next_run_at: string;
  last_run_at: string;
  created_at: string;
  stores: {
    slug: string;
    name: string;
  };
  job_status: {
    id: string;
    name: string;
    next_run_time: string;
    pending: boolean;
    running: boolean;
  } | null;
  description: string;
}

interface ScheduleConfig {
  schedule_types: Record<string, string>;
  common_patterns: Record<string, string>;
  default_timezone: string;
  default_schedules: Record<string, string>;
}

const SCHEDULE_TYPE_COLORS = {
  weekly_price_update: "bg-blue-100 text-blue-800 border-blue-200",
  daily_price_check: "bg-green-100 text-green-800 border-green-200",
  full_catalog_sync: "bg-purple-100 text-purple-800 border-purple-200",
  promotional_scan: "bg-orange-100 text-orange-800 border-orange-200",
};

const StoreSchedulesPage = () => {
  const { success, error: errorToast, info } = useToast();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [config, setConfig] = useState<ScheduleConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedStore, setSelectedStore] = useState<string>("");
  const [isCreating, setIsCreating] = useState(false);
  
  // New schedule form state
  const [newSchedule, setNewSchedule] = useState({
    store_id: "",
    schedule_type: "weekly_price_update",
    cron_expression: "",
    timezone: "Europe/Amsterdam"
  });

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [schedulesRes, storesRes, configRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/scheduling/schedules`),
        fetch(`${BACKEND_URL}/api/scheduling/stores`),
        fetch(`${BACKEND_URL}/api/scheduling/config`)
      ]);

      if (schedulesRes.ok) {
        const schedulesData = await schedulesRes.json();
        setSchedules(schedulesData.data || []);
      }

      if (storesRes.ok) {
        const storesData = await storesRes.json();
        setStores(storesData.data || []);
      }

      if (configRes.ok) {
        const configData = await configRes.json();
        setConfig(configData.data);
        setNewSchedule(prev => ({ ...prev, timezone: configData.data.default_timezone }));
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
      errorToast({
        title: "Error",
        description: "Failed to load schedule data",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!newSchedule.store_id || !newSchedule.cron_expression) {
      errorToast({
        title: "Error",
        description: "Please fill in all required fields",
      });
      return;
    }

    try {
      const response = await fetch(`${BACKEND_URL}/api/scheduling/schedules`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(newSchedule),
      });

      if (response.ok) {
        success({
          title: "Success",
          description: "Schedule created successfully",
        });
        setIsCreating(false);
        setNewSchedule({
          store_id: "",
          schedule_type: "weekly_price_update",
          cron_expression: "",
          timezone: "Europe/Amsterdam"
        });
        fetchData();
      } else {
        const error = await response.json();
        errorToast({
          title: "Error",
          description: error.detail || "Failed to create schedule",
        });
      }
    } catch (error) {
      console.error("Failed to create schedule:", error);
      errorToast({
        title: "Error",
        description: "Failed to create schedule",
      });
    }
  };

  const handleDeleteSchedule = async (scheduleId: string) => {
    if (!confirm("Are you sure you want to delete this schedule?")) return;

    try {
      const response = await fetch(`${BACKEND_URL}/api/scheduling/schedules/${scheduleId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        success({
          title: "Success",
          description: "Schedule deleted successfully",
        });
        fetchData();
      } else {
        const error = await response.json();
        errorToast({
          title: "Error",
          description: error.detail || "Failed to delete schedule",
        });
      }
    } catch (error) {
      console.error("Failed to delete schedule:", error);
      errorToast({
        title: "Error",
        description: "Failed to delete schedule",
      });
    }
  };

  const handleTriggerManualRun = async (storeSlug: string, scheduleType: string) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/scheduling/schedules/manual-run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          store_slug: storeSlug,
          schedule_type: scheduleType
        }),
      });

      if (response.ok) {
        success({
          title: "Manual Run Started",
          description: `Started manual ${scheduleType} for ${storeSlug}`,
        });
        // Refresh data to see updated job status
        setTimeout(fetchData, 1000);
      } else {
        const error = await response.json();
        errorToast({
          title: "Error",
          description: error.detail || "Failed to start manual run",
        });
      }
    } catch (error) {
      console.error("Failed to trigger manual run:", error);
      errorToast({
        title: "Error",
        description: "Failed to trigger manual run",
      });
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getStatusBadge = (schedule: Schedule) => {
    const { job_status } = schedule;
    
    if (!job_status) {
      return <Badge variant="outline" className="bg-gray-100">No Status</Badge>;
    }

    if (job_status.running) {
      return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Running</Badge>;
    }

    if (job_status.pending) {
      return <Badge className="bg-blue-100 text-blue-800 border-blue-200">Pending</Badge>;
    }

    return <Badge variant="outline" className="bg-green-100 text-green-800 border-green-200">Scheduled</Badge>;
  };

  const filteredSchedules = schedules.filter(schedule => {
    if (selectedStore && schedule.stores.slug !== selectedStore) return false;
    return true;
  });

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="p-6">
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading schedules...</p>
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Store Schedules</h1>
            <p className="text-gray-600 mt-1">Manage automated scraping schedules for all stores</p>
          </div>
          <Button 
            onClick={() => setIsCreating(true)}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <Calendar className="h-4 w-4 mr-2" />
            Create Schedule
          </Button>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Filters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <div className="flex-1">
                <label htmlFor="store-filter" className="block text-sm font-medium text-gray-700 mb-1">
                  Filter by Store
                </label>
                <select
                  id="store-filter"
                  value={selectedStore}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedStore(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm ring-offset-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                >
                  <option value="">All Stores</option>
                  {stores.map((store) => (
                    <option key={store.id} value={store.slug}>
                      {store.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Schedules Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSchedules.map((schedule) => (
            <Card key={schedule.id} className="hover:shadow-lg transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-lg">{schedule.stores.name}</CardTitle>
                    <CardDescription className="mt-1">
                      {schedule.description}
                    </CardDescription>
                  </div>
                  {getStatusBadge(schedule)}
                </div>
                <div className="flex gap-2 mt-2">
                  <Badge 
                    className={SCHEDULE_TYPE_COLORS[schedule.schedule_type as keyof typeof SCHEDULE_TYPE_COLORS] || "bg-gray-100 text-gray-800 border-gray-200"}
                  >
                    {config?.schedule_types[schedule.schedule_type] || schedule.schedule_type}
                  </Badge>
                  {schedule.is_active ? (
                    <Badge className="bg-green-100 text-green-800 border-green-200">Active</Badge>
                  ) : (
                    <Badge variant="outline" className="bg-red-100 text-red-800 border-red-200">Inactive</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-3 text-sm">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-gray-500" />
                    <span className="text-gray-600">Schedule:</span>
                    <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                      {schedule.cron_expression}
                    </code>
                  </div>
                  
                  {schedule.job_status?.next_run_time && (
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-gray-500" />
                      <span className="text-gray-600">Next Run:</span>
                      <span className="font-medium text-gray-900">
                        {formatDate(schedule.job_status.next_run_time)}
                      </span>
                    </div>
                  )}
                  
                  {schedule.last_run_at && (
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-gray-500" />
                      <span className="text-gray-600">Last Run:</span>
                      <span className="text-gray-900">
                        {formatDate(schedule.last_run_at)}
                      </span>
                    </div>
                  )}
                  
                  <div className="flex items-center gap-2">
                    <Settings className="h-4 w-4 text-gray-500" />
                    <span className="text-gray-600">Timezone:</span>
                    <span className="text-gray-900">{schedule.timezone}</span>
                  </div>
                </div>
                
                <div className="flex gap-2 mt-4 pt-3 border-t">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTriggerManualRun(schedule.stores.slug, schedule.schedule_type)}
                    className="flex-1"
                  >
                    <Play className="h-3 w-3 mr-1" />
                    Run Now
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDeleteSchedule(schedule.id)}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {filteredSchedules.length === 0 && (
          <Card>
            <CardContent className="text-center py-12">
              <Calendar className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No schedules found</h3>
              <p className="text-gray-600 mb-4">
                {selectedStore ? `No schedules found for the selected store.` : `No schedules have been created yet.`}
              </p>
              <Button onClick={() => setIsCreating(true)} className="bg-blue-600 hover:bg-blue-700">
                Create Your First Schedule
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Create Schedule Modal */}
        {isCreating && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <Card className="w-full max-w-md">
              <CardHeader>
                <CardTitle>Create New Schedule</CardTitle>
                <CardDescription>
                  Set up an automated scraping schedule for a store
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleCreateSchedule} className="space-y-4">
                  <div>
                    <label htmlFor="store" className="block text-sm font-medium text-gray-700 mb-1">
                      Store *
                    </label>
                    <select
                      id="store"
                      value={newSchedule.store_id}
                      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => 
                        setNewSchedule(prev => ({ ...prev, store_id: e.target.value }))
                      }
                      className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm ring-offset-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                      required
                    >
                      <option value="">Select a store</option>
                      {stores.filter(store => store.is_active).map((store) => (
                        <option key={store.id} value={store.id}>
                          {store.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label htmlFor="schedule-type" className="block text-sm font-medium text-gray-700 mb-1">
                      Schedule Type
                    </label>
                    <select
                      id="schedule-type"
                      value={newSchedule.schedule_type}
                      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => 
                        setNewSchedule(prev => ({ ...prev, schedule_type: e.target.value }))
                      }
                      className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm ring-offset-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                    >
                      {config && Object.entries(config.schedule_types).map(([key, value]) => (
                        <option key={key} value={key}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label htmlFor="cron" className="block text-sm font-medium text-gray-700 mb-1">
                      Cron Expression *
                    </label>
                    <select
                      id="cron"
                      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => 
                        setNewSchedule(prev => ({ ...prev, cron_expression: e.target.value }))
                      }
                      className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm ring-offset-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                    >
                      <option value="">Select a schedule pattern</option>
                      {config && Object.entries(config.common_patterns).map(([key, value]) => (
                        <option key={key} value={key}>
                          {value}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      Or enter a custom cron expression below
                    </p>
                    <Input
                      value={newSchedule.cron_expression}
                      onChange={(e) => setNewSchedule(prev => ({ ...prev, cron_expression: e.target.value }))}
                      placeholder="0 23 * * 1 (Every Monday at 11 PM)"
                      className="mt-2"
                    />
                  </div>

                  <div>
                    <label htmlFor="timezone" className="block text-sm font-medium text-gray-700 mb-1">
                      Timezone
                    </label>
                    <Input
                      id="timezone"
                      value={newSchedule.timezone}
                      onChange={(e) => setNewSchedule(prev => ({ ...prev, timezone: e.target.value }))}
                      placeholder="Europe/Amsterdam"
                    />
                  </div>

                  <div className="flex gap-3 pt-4">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setIsCreating(false)}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      className="flex-1 bg-blue-600 hover:bg-blue-700"
                    >
                      Create Schedule
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default StoreSchedulesPage; 