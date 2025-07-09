import requests
import json
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.grafana import GrafanaManagementClient

def setup_grafana_dashboards():
    """Setup Grafana dashboards and datasources"""
    
    subscription_id = os.environ.get('ARM_SUBSCRIPTION_ID')
    resource_group = os.environ.get('RESOURCE_GROUP')
    
    # Initialize Azure clients
    credential = DefaultAzureCredential()
    grafana_client = GrafanaManagementClient(credential, subscription_id)
    
    # Get Grafana workspaces
    workspaces = grafana_client.grafana.list_by_resource_group(resource_group)
    
    for workspace in workspaces:
        print(f"📊 Found Grafana workspace: {workspace.name}")
        print(f"🌐 Endpoint: {workspace.properties.endpoint}")
        
        # Common AKS monitoring dashboards to import
        dashboards = [
            {
                "name": "AKS Cluster Overview", 
                "url": "https://grafana.com/api/dashboards/8588/revisions/1/download"
            },
            {
                "name": "Kubernetes Pod Monitoring",
                "url": "https://grafana.com/api/dashboards/6417/revisions/1/download"
            },
            {
                "name": "ArgoCD Overview",
                "url": "https://grafana.com/api/dashboards/14584/revisions/1/download"
            }
        ]
        
        print("🎯 Ready to import dashboards:")
        for dashboard in dashboards:
            print(f"  - {dashboard['name']}")

if __name__ == "__main__":
    setup_grafana_dashboards()
