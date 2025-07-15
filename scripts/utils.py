import os
import yaml
from pathlib import Path
import logging
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from rich import print
from string import Template
import shutil
import json
import requests
import argocd

logger = logging.getLogger(__name__)

class AzureKeyVaultManager:
    def __init__(self, vault_url=None, client_id=None, client_secret=None, tenant_id=None):
        self.vault_url = vault_url or os.environ.get('AZURE_KEYVAULT_URL', 'https://oorja-dev-kv-bnk4ys.vault.azure.net/')
        
        if client_id and client_secret and tenant_id:
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            # Use DefaultAzureCredential for OIDC/Managed Identity
            credential = DefaultAzureCredential()
        
        self.client = SecretClient(vault_url=self.vault_url, credential=credential)

    def get_secret(self, secret_name):
        """Retrieve secret from Azure Key Vault"""
        try:
            secret = self.client.get_secret(secret_name)
            logger.info(f"Secret '{secret_name}' retrieved successfully")
            return secret.value
        except Exception as e:
            logger.error(f"Failed to retrieve secret '{secret_name}': {str(e)}")
            raise

    def get_secrets_bulk(self, secret_names):
        """Retrieve multiple secrets from Azure Key Vault"""
        secrets = {}
        for secret_name in secret_names:
            try:
                secrets[secret_name] = self.get_secret(secret_name)
            except Exception as e:
                logger.warning(f"Failed to get secret {secret_name}: {e}")
        return secrets

def azure_get_secret_values(secrets_config):
    """Get secrets from Azure Key Vault"""
    vault_manager = AzureKeyVaultManager(
        vault_url=secrets_config.get('vault_url', 'https://oorja-dev-kv-bnk4ys.vault.azure.net/'),
        client_id=secrets_config.get('client_id'),
        client_secret=secrets_config.get('client_secret'),
        tenant_id=secrets_config.get('tenant_id')
    )
    
    secret_names = secrets_config.get('secret_names', [])
    return vault_manager.get_secrets_bulk(secret_names)

def set_env_vars(vars_list):
    """Set environment variables from list or dict"""
    if isinstance(vars_list, list):
        for vars_dict in vars_list:
            for key, value in vars_dict.items():
                os.environ[key] = str(value)
    elif isinstance(vars_list, dict):
        for key, value in vars_list.items():
            os.environ[key] = str(value)

def prepare_genesis_secrets():
    """Prepare Genesis frontend secrets for Application Gateway access"""
    return {
        'GENESIS_USER_ID': 'Harman-DTS',
        'GENESIS_PASSWORD': os.environ.get('GENESIS_PAT_TOKEN'),
        'GENESIS_REPO_URL': 'https://github.com/HARMAN-DTS/Genesis'
    }

def dynamic_width_print():
    """Print dynamic width separator"""
    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    print('-' * width)

def print_response(response, **kwargs):
    """Print formatted response with status"""
    method = kwargs.get('method', 'unknown')
    service_name = kwargs.get('service_name', 'service')
    service_type = kwargs.get('service_type', 'resource')
    
    if hasattr(response, 'status_code'):
        status_code = response.status_code
    elif isinstance(response, tuple) and len(response) > 1:
        status_code = response[1]
    else:
        status_code = 200 if response else 500
    
    if status_code in [200, 201, 202]:
        print(f"[bold green] Successfully applied '[bright_blue]{method}[/bright_blue]' on [bright_cyan]{service_name}[/bright_cyan] {service_type}!\n")
    else:
        print(f"[bold red] Failed to perform {method} on {service_name} {service_type}. Status Code: {status_code}")
    
    dynamic_width_print()

def prepare_payload_data(meta_yaml_file, service_type):
    """Prepare payload data for ArgoCD services with Azure Key Vault support"""
    service_yamls = {}
    meta_yaml_dir = meta_yaml_file.parent
    meta_yaml_config = load_yaml(meta_yaml_file)
    
    for service in meta_yaml_config[service_type]:
        service_conf = meta_yaml_config[service_type][service]
        if service_conf['enabled'] == False and service_conf['method'] != 'delete':
            service_conf['method'] = 'delete'
            
        secret_exists = lambda: service_conf.get('secrets', None)
        if secret_exists():
            # Handle Azure Key Vault secrets
            if service_conf['secrets'].get('azure', None):
                azure_secrets = service_conf['secrets']['azure']
                secret_values = azure_get_secret_values(azure_secrets)
                set_env_vars(secret_values)
    
        if (service_yaml := (meta_yaml_dir / service_type / f"{service}.yaml")).exists():
            if secret_exists():
                service_yamls[service] = load_yaml(service_yaml, as_string=True)
            else:
                service_yamls[service] = load_yaml(service_yaml)
        
        service_yamls[service]['method'] = service_conf['method']
    
    return service_yamls

def load_yaml(file_path, as_string: bool = False):
    """Load YAML file with optional template substitution"""
    if not as_string:
        return yaml.safe_load(open(file_path)) or {}
    
    with open(file_path, "r", encoding="utf-8") as file:
        yaml_template = Template(file.read())
        yaml_string = yaml_template.safe_substitute(os.environ)
        return yaml.safe_load(yaml_string) or {}

def get_argocd_jwt_token(server_url, username, password, verify_ssl=False):
    """Get proper JWT token from ArgoCD login API"""
    server_url = server_url.rstrip('/')
    
    # Now that routing is fixed, try the standard endpoint
    login_url = f"{server_url}/api/v1/session"
    
    login_data = {
        "username": username,
        "password": password
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        print(f"🔑 Getting JWT token from: {login_url}")
        
        response = requests.post(
            login_url,
            json=login_data,
            headers=headers,
            verify=verify_ssl,
            timeout=30
        )
        
        print(f"📡 Login response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            token = result.get('token')
            
            if token:
                print("✅ Successfully obtained JWT token from API")
                print(f"📋 Token length: {len(token)} characters")
                return token
            else:
                print("❌ No token in response")
                print(f"Response: {result}")
        else:
            print(f"❌ Login failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Login request failed: {str(e)}")
    
    return None

def get_argocd_client():
    """Get ArgoCD client with proper JWT token authentication"""
    argocd_url = os.environ.get('ARGOCD_URL')
    admin_password = os.environ.get('ARGOCD_ADMIN_PASSWORD')
    verify_ssl = os.environ.get('ARGOCD_VERIFY_SSL', 'false').lower() == 'true'
    
    print(f"🔗 Connecting to ArgoCD at: {argocd_url}")
    print(f"🔒 SSL Verification: {verify_ssl}")
    
    # Set basic environment variables
    os.environ['ARGOCD_URL'] = argocd_url
    os.environ['ARGOCD_VERIFY_SSL'] = str(verify_ssl).lower()
    
    # Get proper JWT token
    jwt_token = get_argocd_jwt_token(argocd_url, 'admin', admin_password, verify_ssl)
    
    if jwt_token:
        print("✅ Setting JWT token in environment")
        os.environ['ARGOCD_AUTH_TOKEN'] = jwt_token
        
        try:
            client = argocd.ArgoCDClient()
            print(f"✅ ArgoCD client created successfully")
            return client
        except Exception as e:
            print(f"❌ Client creation failed: {str(e)}")
            raise e
    else:
        raise Exception("Could not obtain valid JWT token from ArgoCD API")
