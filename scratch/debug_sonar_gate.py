import os
import sys
import requests

def debug_sonar():
    host_url = os.environ.get("SONAR_HOST_URL")
    token = os.environ.get("SONAR_TOKEN")
    
    if not host_url or not token:
        print("SONAR_HOST_URL or SONAR_TOKEN is not set in the environment.")
        sys.exit(1)
        
    print(f"Connecting to SonarQube host: {host_url}")
    
    # Authenticate using the token via Basic Auth (token as username, empty password)
    session = requests.Session()
    session.auth = (token, "")
    
    project_key = "zotero-cli"
    url = f"{host_url.rstrip('/')}/api/qualitygates/project_status"
    params = {"projectKey": project_key}
    
    try:
        response = session.get(url, params=params, timeout=30)
        print(f"HTTP Status Code: {response.status_code}")
        
        if response.status_code == 200:
            status_data = response.json()
            project_status = status_data.get("projectStatus", {})
            print("\n=== SonarQube Quality Gate Project Status ===")
            print(f"Status: {project_status.get('status')}")
            
            conditions = project_status.get("conditions", [])
            print("\nConditions:")
            for cond in conditions:
                status = cond.get("status")
                metric = cond.get("metricKey")
                operator = cond.get("comparator")
                error_threshold = cond.get("errorThreshold")
                actual_value = cond.get("actualValue")
                
                print(f"  - Metric: {metric:<30} | Status: {status:<8} | Actual: {actual_value:<10} | Threshold: {operator} {error_threshold}")
        else:
            print(f"Failed to fetch project status: {response.text}")
    except Exception as e:
        print(f"Error connecting to SonarQube: {e}")

if __name__ == "__main__":
    debug_sonar()
