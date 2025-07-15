import os
import sys
import argparse
import argocd
from pathlib import Path
import time
from rich import print
import utils as argocd_utils

def filter_query_params(query_params, method):
    if method == 'create':
        allowed_params = {'upsert', 'creds_only'}
    elif method == 'delete':
        allowed_params = {'force_refresh', 'app_project'}
    # elif method == 'update':              # No query params in schema
    #     allowed_params = {}
    return {k: v for k, v in query_params.items() if k in allowed_params}

def repository_exists(client, name, **kwargs):
    try:
        _ = client.repos.repository_service_get(name)
        return True
    except argocd.rest.ApiException:
        print('[yellow] Repository not found!')
        return False
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Argo CD Repository service operations")
    parser.add_argument('-l', '--host-url', help="Hosted ArgoCD App URL",)
    parser.add_argument('-t', '--token', help="ArgoCD user account OAuth token with repository permissions")
    parser.add_argument('--verify-ssl', choices=["true", "false"], help="ArgoCD username", type=str)
    parser.add_argument('-f', '--config-file', help="ArgoCD API service Metadata YAML file", required=True)
    parser.add_argument('-s', '--service-type', help="Name of the directory to be used for repository services", default='repositories')
    parser.add_argument("-u", "--username", help="ArgoCD username", required=False)
    parser.add_argument("-p", "--password", help="ArgoCD password", required=False)
    args = parser.parse_args()

    if args.host_url:
        os.environ["ARGOCD_URL"] = args.host_url

    if args.token:
        os.environ["ARGOCD_AUTH_TOKEN"] = args.token

    if args.verify_ssl:
        os.environ["ARGOCD_VERIFY_SSL"] = args.verify_ssl

    if args.config_file:
        meta_yaml_file = Path(args.config_file)
        payloads = argocd_utils.prepare_payload_data(meta_yaml_file, service_type=args.service_type)
        if not payloads:
            print(f"[red] Failed to load config file:[/red] {args.config_file} \n[yellow] Reason: No repositories enabled![/yellow]")
            sys.exit(0)
        
        client = argocd_utils.get_argocd_client()
        res = None
        for repo, body in payloads.items():
            _method = body.pop('method')
            query_params = body.pop('query_params', {})
            
            repo_exists = repository_exists(client, body['spec']['repo']) 
            if not repo_exists and _method == 'delete':
                argocd_utils.dynamic_width_print()
                continue
            
            query_params = filter_query_params(query_params=query_params, method=_method)
            if _method == "create":
                if body["permission"] == "write":
                    res = client.repos.repository_service_create_write_repository(body=body["spec"], _return_http_data_only=False, **query_params)
                else:
                    res = client.repos.repository_service_create_repository(body=body["spec"], _return_http_data_only=False, **query_params)
            elif _method == "update":
                if body["permission"] == "write":
                    res = client.repos.repository_service_update_write_repository(body['spec']['repo'], body=body["spec"], _return_http_data_only=False, **query_params)
                else:
                    res = client.repos.repository_service_update_repository(body['spec']['repo'], body=body["spec"], _return_http_data_only=False, **query_params)

            elif _method == "delete":
                if body["permission"] == "write":
                    res = client.repos.repository_service_delete_write_repository(body['spec']['repo'], _return_http_data_only=False, **query_params)
                else:
                    res = client.repos.repository_service_delete_repository(body['spec']['repo'], _return_http_data_only=False, **query_params)
            # Check if the request was successful

            argocd_utils.print_response(res, method=_method, service_name=repo, service_type='repository')
            time.sleep(2)
            
    





