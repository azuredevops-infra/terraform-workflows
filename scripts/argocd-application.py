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
        allowed_params = {'upsert', 'validate'}
    elif method == 'delete':
        allowed_params = {'name', 'cascade', 'propagation_policy', 'app_namespace', 'project'}
    elif method == 'update':
        allowed_params = {'validate', 'project'}
    return {k: v for k, v in query_params.items() if k in allowed_params}
        
def application_exists(client, name, **kwargs):
    try:
        _ = client.applications.application_service_get(name, **kwargs)
        return True
    except argocd.rest.ApiException:
        print('[yellow] Application not found!')
        return False
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Argo CD Application service operations")
    parser.add_argument('-l', '--host-url', help="Hosted ArgoCD App URL",)
    parser.add_argument('-t', '--token', help="ArgoCD user account OAuth token with applications permissions", required=False)
    parser.add_argument('--verify-ssl', choices=["true", "false"], help="ArgoCD username", type=str)
    parser.add_argument('-f', '--config-file', help="ArgoCD Applications service Metadata YAML file", required=True)
    parser.add_argument('-s', '--service-type', help="Name of the directory to be used for application services", default='applications')
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
            print(f"Failed to load config file: {args.config_file}")
            sys.exit(1)
            
        client = argocd.ArgoCDClient()
        res = None
        for app, body in payloads.items():
            _method = body.pop('method')
            query_params  = body.pop('query_params', {})
            
            app_exists = application_exists(client, body['metadata']['name']) 
            if not app_exists and _method == 'delete':
                argocd_utils.dynamic_width_print()
                continue
            
            query_params = filter_query_params(query_params=query_params, method=_method)
            if _method == "create":
                res = client.applications.application_service_create(body=body, _return_http_data_only=False, **query_params)
            elif _method == "update":
                res = client.applications.application_service_update(body['metadata']['name'], body=body, _return_http_data_only=False, **query_params)
            elif _method == "delete":
                res = client.applications.application_service_delete(body['metadata']['name'], _return_http_data_only=False, **query_params)
                
            else:
                print(f'Error! Invalid method name passed: {_method}')
            
            argocd_utils.print_response(res, method=_method, service_name=app, service_type='application')
            time.sleep(2)
