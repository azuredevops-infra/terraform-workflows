import os
import yaml
from pathlib import Path
import os
import boto3
import json
import logging
from rich import print
from string import Template
import shutil

logger = logging.getLogger(__name__)

class AWSSecretsManager:
    def __init__(self, secretsmanager_client):
        self.client = secretsmanager_client


    def get_secret(self, secret_name):
        """
        Retrieve individual secrets from AWS Secrets Manager using the get_secret_value API.
        This function assumes the stack mentioned in the source code README has been successfully deployed.
        This stack includes 7 secrets, all of which have names beginning with "mySecret".

        :param secret_name: The name of the secret fetched.
        :type secret_name: str
        """
        try:
            get_secret_value_response = self.client.get_secret_value(
                SecretId=secret_name
            )
            logging.info("Secret retrieved successfully.")
            return get_secret_value_response["SecretString"]
        except self.client.exceptions.ResourceNotFoundException:
            msg = f"The requested secret {secret_name} was not found."
            logger.info(msg)
            return msg
        except Exception as e:
            logger.error(f"An unknown error occurred: {str(e)}.")
            raise
        
def aws_get_secret_values(secrets: str | list):


    # Get a secret
    if isinstance(secrets, str):
        secrets = [secrets]
    
    secrets_list = []
    for secret in secrets:
        secrets_client = boto3.client('secretsmanager', region_name=secret['region'])
        # Create an instance of the wrapper
        secret_wrapper = AWSSecretsManager(secrets_client)
        secret_value = secret_wrapper.get_secret(secret['name'])
        secrets_list.append(json.loads(secret_value))
    
    return secrets_list

def set_env_vars(vars_list: list[dict]):
    for vars in vars_list:
        for key, value in vars.items():
            os.environ[key] = value
            
def dynamic_width_print():
    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    print('-' * width)

def print_response(response, **kwargs):
    method = kwargs.get('method')
    service_name = kwargs.get('service_name')
    service_type = kwargs.get('service_type')
    if response[1] == 200:
        print(f"[bold green] Successfully applied '[bright_blue]{method}[/bright_blue]' on [bright_cyan]{service_name}[/bright_cyan] {service_type} YAML configuration!\n")
    else:
        print(f"Failed to perform repository service API request. Status Code: {response[1]}")
        print(f"Response: {response[1]}")
        print(f"Response Headers: {response[2]}")
    
    dynamic_width_print()
    
def prepare_payload_data(meta_yaml_file, service_type):
    service_yamls = {}
    meta_yaml_dir = meta_yaml_file.parent
    meta_yaml_config = load_yaml(meta_yaml_file)
    for service in meta_yaml_config[service_type]:
        
        service_conf = meta_yaml_config[service_type][service]
        if service_conf['enabled'] == False and service_conf['method'] != 'delete':
            service_conf['method'] = 'delete'
            
        secret_exists = lambda: service_conf.get('secrets', None)
        if secret_exists():
            if service_conf['secrets'].get('aws', None):
                aws_secrets = service_conf['secrets']['aws']
                secret_json = aws_get_secret_values(aws_secrets)
                set_env_vars(secret_json)
    
        if (service_yaml := (meta_yaml_dir / service_type / f"{service}.yaml")).exists():
            if secret_exists():
                service_yamls[service] = load_yaml(service_yaml, as_string=True)
            else:
                service_yamls[service] = load_yaml(service_yaml)
        
        service_yamls[service]['method'] = service_conf['method']
    
    return service_yamls

            
    

def load_yaml(file_path, as_string: bool = False):
    if not as_string:
        return yaml.safe_load(open(file_path)) or {}
    
    with open(file_path, "r", encoding="utf-8") as file:
        yaml_template = Template(file.read())
        yaml_string = yaml_template.safe_substitute(os.environ)
        return yaml.safe_load(yaml_string) or {}
        

# if __name__ == '__main__':
#     # res = load_yaml('argocd-configs/repositories/genesis.yaml', as_string=True)
#     # print(res)
#     meta_yaml_file = Path('argocd-configs/repository.yaml')
#     argocd_service_type = 'repositories'
#     result = prepare_payload_data(meta_yaml_file, service_type=argocd_service_type)
#     print(result)