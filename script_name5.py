import requests
import subprocess
from typing import List, Dict
import time
import sys
import os

# Constants
NUM_REQUESTS = 50  # Adjust as needed
INGRESS_NAME = "add-app-ingress"
DEPLOYMENT_NAME = "add-app"
NAMESPACE = "default"  # Adjust if your namespace is different
LOCAL_PORT = 8080  # Port for local/port-forwarded connection

def get_ingress_host(ingress_name: str) -> str:
    try:
        result = subprocess.run(
            [
                "kubectl", "get", "ingress", ingress_name,
                "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}{.status.loadBalancer.ingress[0].hostname}"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        ingress_host = result.stdout.strip()
        if not ingress_host:
            raise ValueError("Ingress host is empty")
        return ingress_host
    except subprocess.CalledProcessError as e:
        print(f"Error getting Ingress host: {e}")
        return ""

def get_running_pods(deployment_name: str, namespace: str) -> List[str]:
    try:
        command = [
            "kubectl", "get", "pods", "-n", namespace,
            "-l", f"app={deployment_name}",
            "-o", "jsonpath={.items[*].metadata.name}"
        ]
        print(f"Running command: {' '.join(command)}")
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        pods = result.stdout.strip().split()
        print(f"Pods found: {pods}")
        
        if not pods:
            raise ValueError("No running pods found")
        return pods
    except subprocess.CalledProcessError as e:
        print(f"Error getting running pods: {e}")
        return []

def is_running_in_cluster() -> bool:
    return os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token")

def get_connection_info():
    if is_running_in_cluster():
        ingress_host = get_ingress_host(INGRESS_NAME)
        if not ingress_host:
            print("Failed to get Ingress host. Exiting.")
            sys.exit(1)
        return ingress_host, 80  # Assuming standard HTTP port for Ingress
    else:
        print("Running locally. Using port-forwarded connection.")
        return "localhost", LOCAL_PORT

HOST, PORT = get_connection_info()
PODS = get_running_pods(DEPLOYMENT_NAME, NAMESPACE)

if not PODS:
    print("No running pods found. Exiting.")
    sys.exit(1)

print(f"Host: {HOST}")
print(f"Port: {PORT}")
print(f"Pods ({len(PODS)}): {', '.join(PODS)}")

def round_robin_access(num_requests: int) -> List[Dict]:
    accessed_pods = []
    index = 0  # Start from the first pod

    for _ in range(num_requests):
        pod = PODS[index]
        response = send_request_to_pod(pod)
        accessed_pods.append(response)
        
        # Update index for next iteration (cycle through pods)
        index = (index + 1) % len(PODS)

    return accessed_pods

def send_request_to_pod(pod: str) -> Dict:
    url = f"http://{HOST}:{PORT}/"
    start_time = time.time()
    try:
        response = requests.get(url, headers={"Host": pod}, timeout=5)
        elapsed_time = time.time() - start_time
        return {
            "pod": pod,
            "status": response.status_code,
            "content": response.text,
            "response_time": elapsed_time
        }
    except requests.RequestException as e:
        elapsed_time = time.time() - start_time
        return {
            "pod": pod,
            "status": "Error",
            "content": str(e),
            "response_time": elapsed_time
        }

def analyze_results(accessed_pods: List[Dict]) -> None:
    pod_counts = {pod: 0 for pod in PODS}
    total_requests = len(accessed_pods)
    total_response_time = 0

    print("\nDetailed access pattern:")
    for i, response in enumerate(accessed_pods, 1):
        pod = response["pod"]
        status = response["status"]
        response_time = response["response_time"]
        pod_counts[pod] += 1
        total_response_time += response_time
        print(f"Request {i:2d}: Pod: {pod}")
        print(f"    Status: {status}")
        print(f"    Response Time: {response_time:.4f}s")
        print(f"    Content: {response['content'][:100]}...")  # Print first 100 characters of content
        print()

    print("\nPod distribution summary:")
    for pod, count in pod_counts.items():
        percentage = (count / total_requests) * 100
        print(f"  {pod}: {count} requests ({percentage:.2f}%)")

    print(f"\nTotal Requests: {total_requests}")
    print(f"Average Response Time: {total_response_time / total_requests:.4f}s")

if __name__ == "__main__":
    start_time = time.time()
    accessed_pods = round_robin_access(NUM_REQUESTS)
    end_time = time.time()

    print(f"\nRound-robin access test completed in {end_time - start_time:.2f} seconds.")
    analyze_results(accessed_pods)
