"use client";

import { useState, useEffect } from 'react';
import { Metadata } from 'next'
import DashboardLayout from '@/components/layout/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, PlayCircle, StopCircle, RefreshCw, Activity } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface Agent {
  id: string;
  name: string;
  type: string;
  status: any;
}

interface AgentsResponse {
  agents: Agent[];
  available: boolean;
  message?: string;
}

const ScrapersPage = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentsAvailable, setAgentsAvailable] = useState(false);
  const { success, error: errorToast, info } = useToast();

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/agents/');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data: AgentsResponse = await response.json();
      setAgents(data.agents || []);
      setAgentsAvailable(data.available);
      if (data.message) {
        setError(data.message);
      } else {
        setError(null);
      }
    } catch (err) {
      console.error('Failed to fetch agents:', err);
      setError('Failed to connect to backend API');
    } finally {
      setLoading(false);
    }
  };

  const testAgentsSystem = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/agents/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log('Agents test result:', data);
      success({
        title: "Agents Test Completed",
        description: `Found ${data.agent_count} agents - ${data.test_status}`,
        duration: 8000,
      });
    } catch (err) {
      console.error('Failed to test agents:', err);
      errorToast({
        title: "Test Failed",
        description: "Failed to test agents system",
      });
    }
  };

  const startAgent = async (agentId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/agents/${agentId}/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log('Start agent result:', data);
      success({
        title: "Agent Started",
        description: `${agentId} scraper started successfully`,
      });
      fetchAgents();
    } catch (err) {
      console.error(`Failed to start agent ${agentId}:`, err);
      errorToast({
        title: "Failed to Start Agent",
        description: `Unable to start ${agentId} scraper`,
      });
    }
  };

  const stopAgent = async (agentId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/agents/${agentId}/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log('Stop agent result:', data);
      success({
        title: "Agent Stopped",
        description: `${agentId} scraper stopped successfully`,
      });
      fetchAgents();
    } catch (err) {
      console.error(`Failed to stop agent ${agentId}:`, err);
      errorToast({
        title: "Failed to Stop Agent",
        description: `Unable to stop ${agentId} scraper`,
      });
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const getStatusBadge = (available: boolean) => {
    if (available) {
      return <Badge className="bg-green-500">Available</Badge>;
    } else {
      return <Badge variant="destructive">Not Available</Badge>;
    }
  };

  const handleRefresh = () => {
    fetchAgents();
  };

  return (
    <DashboardLayout>
      <div className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between space-y-2">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Scrapers</h2>
            <p className="text-muted-foreground">
              Manage scraper agents for Dutch supermarkets
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Button onClick={handleRefresh} variant="outline">
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={testAgentsSystem}>
              <Activity className="mr-2 h-4 w-4" />
              Test System
            </Button>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Agents System Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">
                  Backend Connection: {loading ? 'Checking...' : 'Connected'}
                </p>
                <p className="text-sm text-muted-foreground">
                  Agents Available: {getStatusBadge(agentsAvailable)}
                </p>
                {error && (
                  <div className="flex items-center gap-2 mt-2">
                    <AlertCircle className="h-4 w-4 text-amber-500" />
                    <p className="text-sm text-amber-600">{error}</p>
                  </div>
                )}
              </div>
              <div>
                <p className="text-2xl font-bold">{agents.length}</p>
                <p className="text-sm text-muted-foreground">Total Agents</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              System Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-green-600">53,237</p>
                <p className="text-sm text-muted-foreground">Total Products</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-600">5</p>
                <p className="text-sm text-muted-foreground">Active Stores</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-purple-600">52,715</p>
                <p className="text-sm text-muted-foreground">Store Products</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-orange-600">52,709</p>
                <p className="text-sm text-muted-foreground">Current Prices</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(5)].map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardHeader>
                  <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                  <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="h-3 bg-gray-200 rounded"></div>
                    <div className="h-3 bg-gray-200 rounded w-5/6"></div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { name: 'Albert Heijn', products: 20275, lastScrape: '2 hours ago' },
              { name: 'Jumbo', products: 17024, lastScrape: '45 min ago' },
              { name: 'Etos', products: 10117, lastScrape: '1 hour ago' },
              { name: 'Dirk', products: 5299, lastScrape: '30 min ago' },
              { name: 'Hoogvliet', products: 0, lastScrape: 'Not scraped yet' }
            ].map((store, index) => (
              <Card key={store.name}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    {store.name} Agent
                    <Badge variant={agentsAvailable ? "default" : "secondary"}>
                      {agentsAvailable ? "Active" : "Mock"}
                    </Badge>
                  </CardTitle>
                  <CardDescription>
                    Scraper agent for {store.name} {store.name === 'Etos' ? 'pharmacy/beauty' : 'supermarket'}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Status:</span>
                      <Badge variant={
                        store.products > 0 ? "default" : 
                        agentsAvailable ? "outline" : "secondary"
                      }>
                        {store.products > 0 ? "Ready" : 
                         store.name === 'Hoogvliet' ? "Needs Scraping" : 
                         agentsAvailable ? "Ready" : "Not Available"}
                      </Badge>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Products:</span>
                      <span className={store.products === 0 ? "text-muted-foreground" : ""}>
                        {store.products > 0 ? store.products.toLocaleString() : "No data"}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Last Scrape:</span>
                      <span className={store.products === 0 ? "text-muted-foreground" : ""}>
                        {store.lastScrape}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => agentsAvailable ? startAgent(store.name.toLowerCase().replace(' ', '_')) : info({
                        title: "Backend Not Ready",
                        description: `${store.name} agent is not available`,
                      })}
                      className="flex-1"
                      disabled={!agentsAvailable}
                    >
                      <PlayCircle className="mr-2 h-4 w-4" />
                      {store.products === 0 ? "Start Scrape" : "Start"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => agentsAvailable ? stopAgent(store.name.toLowerCase().replace(' ', '_')) : info({
                        title: "Backend Not Ready",
                        description: `${store.name} agent is not available`,
                      })}
                      className="flex-1"
                      disabled={!agentsAvailable}
                    >
                      <StopCircle className="mr-2 h-4 w-4" />
                      Stop
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>API Testing</CardTitle>
            <CardDescription>
              Test the agents API endpoints directly
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => window.open('http://localhost:8000/docs', '_blank')}
                >
                  Open API Docs
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={testAgentsSystem}
                >
                  Test Agents System
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={handleRefresh}
                >
                  Refresh Agents
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
};

export default ScrapersPage; 