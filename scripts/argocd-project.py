import os
import sys
import argparse
import argocd
from pathlib import Path
from rich import print
import utils as argocd_utils

def project_exists(client, name, **kwargs):
    try:
        _ = client.projects.project_service_get(name, **kwargs)
        return True
    except argocd.rest.ApiException:
        print('[yellow] Project not found!')
        return False
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Argo CD Application service operations")
    parser.add_argument('-l', '--host-url', help="Hosted ArgoCD App URL",)
    parser.add_argument('-t', '--token', help="ArgoCD user account OAuth token with applications permissions", required=False)
    parser.add_argument('--verify-ssl', choices=["true", "false"], help="ArgoCD username", type=str)
    parser.add_argument('-f', '--config-file', help="ArgoCD Project service Metadata YAML file", required=True)
    parser.add_argument('-s', '--service-type', help="Name of the directory to be used for project services", default='projects')
    
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
            print(f"[red] Failed to load config file:[/red] {args.config_file} \n[yellow] Reason: No projects enabled![/yellow]")
            sys.exit(0)
            
        client = argocd_utils.get_argocd_client()
        res = None
        for proj, body in payloads.items():
            _method = body.pop('method')
            is_upsert = body.pop('upsert', False)
            
            proj_exists = project_exists(client, body['metadata']['name']) 
            if not proj_exists and _method == 'delete':
                argocd_utils.dynamic_width_print()
                continue
            
            body = {'project': body, 'upsert': is_upsert}
            if _method == "create":
                res = client.projects.project_service_create(body=body, _return_http_data_only=False)
            elif _method == "update":
                res = client.projects.project_service_update(body['project']['metadata']['name'], body=body, _return_http_data_only=False)
            elif _method == "delete":
                res = client.projects.project_service_delete(body['project']['metadata']['name'], _return_http_data_only=False)
        
            argocd_utils.print_response(res, method=_method, service_name=proj, service_type='project')
                
