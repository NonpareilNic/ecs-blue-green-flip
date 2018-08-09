import boto3
import ruamel.yaml
import git


DASHBOARD_LIVE = 'webaddress.com.'
DASHBOARD_DEMO = 'demo.webaddress.com.'
API_LIVE = 'api.webaddress.com'
API_DEMO = 'api-demo.webaddress.com'
HOSTED_ZONE_ID = '/hostedzone/M4D3UPH4SH'
PIPELINE_FILE = 'bitbucket-pipelines.yml'

REGION = 'eu-west-1'
REST_API_ID = 'm4d3uph4sh'

class flip_blue_green:
    def __init__(self):
        self.current_live_dashboard_alias = "No current live dashboard yet"
        self.current_demo_dashboard_alias = "No current demo dashboard yet"
        self.current_live_api_domain = "No current live api yet"
        self.current_demo_api_domain = "No current demo api yet"

        self.blue = "Not yet assigned"
        self.green = "Not yet assigned"


        self.client = boto3.client('route53')
        self.api_client = boto3.client('apigateway')

    def flip_dashboard_route_53(self):
        prior_record_set_result = self.client.list_resource_record_sets(HostedZoneId=HOSTED_ZONE_ID)
        self.assign_record_sets(prior_record_set_result)
        # self.validate_colors()

        self.flip_colors()

        final_record_set_results = self.client.list_resource_record_sets(HostedZoneId=HOSTED_ZONE_ID)
        self.assign_record_sets(final_record_set_results)
        self.validate_colors()

        if self.blue == "demo":
            self.flip_demo_yaml("BLUE", PIPELINE_FILE)
        elif self.green == "demo":
            self.flip_demo_yaml("GREEN", PIPELINE_FILE)
        else:
            print("ERROR: blue and/or green are not assigned. Neither showed up as 'demo'")

        self.git_push()

    def validate_colors(self):
        if self.current_live_dashboard_alias['DNSName'].split('.')[0] == 'blue' and \
                self.current_live_api_domain['stage'] == 'blue':
            print("Current live is Blue")
            self.blue = 'live'
        elif self.current_live_dashboard_alias['DNSName'].split('.')[0] == 'green' and \
                self.current_live_api_domain['stage'] == 'green':
            print("Current live is Green")
            self.green = 'live'
        else:
            print("ERROR: live api and live dashboard have different colors.")

        if self.current_demo_dashboard_alias['DNSName'].split('.')[0] == 'blue' and \
                self.current_demo_api_domain['stage'] == 'blue':
            print("Current demo is Blue")
            self.blue = 'demo'
        elif self.current_demo_dashboard_alias['DNSName'].split('.')[0] == 'green' and \
                self.current_demo_api_domain['stage'] == 'green':
            print("Current demo is Green")
            self.green = 'demo'
        else:
            print("ERROR: demo api and demo dashboard have different colors.")

        if self.green == self.blue:
            print("ERROR: blue and green are both "+ self.green)

    def assign_record_sets(self,record_set_result):
        for record_set in record_set_result['ResourceRecordSets']:
            if 'AliasTarget' in record_set:
                if record_set['Name'] == DASHBOARD_LIVE:
                    self.current_live_dashboard_alias = record_set['AliasTarget']
                    print(DASHBOARD_LIVE + "is currently attached to " + str(self.current_live_dashboard_alias))
                if record_set['Name'] == DASHBOARD_DEMO:
                    self.current_demo_dashboard_alias = record_set['AliasTarget']
                    print(DASHBOARD_DEMO + "is currently attached to " + str(self.current_demo_dashboard_alias))
                if record_set['Name'] == API_LIVE:
                    self.current_live_api_alias = record_set['AliasTarget']
                    print(API_LIVE + "is currently attached to " + str(self.current_live_api_alias))
                if record_set['Name'] == API_DEMO:
                    self.current_demo_api_alias = record_set['AliasTarget']
                    print(API_DEMO + "is currently attached to " + str(self.current_demo_api_alias))

    def flip_colors(self):
        flip_comment = 'flipping dashboard '+self.blue+' to green and '+self.green+' to blue'
        print(flip_comment)
        self.client.change_resource_record_sets(
            HostedZoneId=HOSTED_ZONE_ID,
            ChangeBatch={
                'Comment': flip_comment,
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': DASHBOARD_LIVE,
                            'Type': 'A',
                            'AliasTarget': self.current_demo_dashboard_alias
                        }
                    },
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': DASHBOARD_DEMO,
                            'Type': 'A',
                            'AliasTarget': self.current_live_dashboard_alias
                        }
                    }
                ]
            }
        )
        print('flip complete.')

    def flip_demo_yaml(self, color, fname):
        yaml = ruamel.yaml.YAML()
        # yaml.preserve_quotes = True
        with open(fname) as fp:
            data = yaml.load(fp)

        for stepDict in data['pipelines']['branches']['dev']:
            row=stepDict['step']['script'][1]
            if 'export COLOR=' in row:
                print("row was "+row)
                row = "export COLOR="+color
                print("row is "+row)
                stepDict['step']['script'][1]=row

        with open(fname, "w") as fp:
            yaml.dump(data, fp)

    def git_push(self):
        commit_message = "Flipped Blue to "+self.blue+" and Green to "+self.green
        print(commit_message)
        repo = git.Repo(".")
        repo.git.add("bitbucket-pipelines.yml")
        repo.git.commit("-m "+commit_message)
        print("To kick off changes, please type 'git push' into your git terminal")

    def flip_api_custom_domains(self):
        starting_live, starting_demo = self.get_current_api_colors()
        print('Flipping API colors')
        self.flip_api_colors()
        # self.get_current_api_colors()

    def get_current_api_colors(self):
        domains_response = self.api_client.get_domain_names()
        for item in domains_response['items']:
            if item['domainName'] == API_LIVE:
                self.current_live_api_domain = item
                mappings_live_response = self.api_client.get_base_path_mappings(
                    domainName=self.current_live_api_domain['domainName'])
                demo_stage = mappings_live_response['items'][0]['stage']
                self.current_live_api_domain['stage'] = demo_stage
                print('Live API is currently ' + str(self.current_live_api_domain['stage']))
            if item['domainName'] == API_DEMO:
                self.current_demo_api_domain = item
                mappings_demo_response = self.api_client.get_base_path_mappings(
                    domainName=self.current_demo_api_domain['domainName'])
                demo_stage = mappings_demo_response['items'][0]['stage']
                self.current_demo_api_domain['stage'] = demo_stage
                print('Demo API is currently ' + str(self.current_demo_api_domain['stage']))
        return self.current_live_api_domain['stage'], self.current_demo_api_domain['stage']

    def flip_api_colors(self):
        # Switch live mapping to point to previous demo
        new_live_stage = self.switch_base_path_mapping(self.current_live_api_domain)
        # Deploy new live stage
        deploy_response = self.api_client.create_deployment(
                                    restApiId=REST_API_ID,
                                    stageName=new_live_stage)
        print("Deployed "+new_live_stage+" at "+str(deploy_response['createdDate'])+" with deployment ID "+deploy_response['id'])
        # Delete the base path mapping of previous live stage
        self.api_client.delete_base_path_mapping(
            domainName=API_DEMO,
            basePath='(none)'
        )
        # # Delete the previous live stage
        self.api_client.delete_stage(
            restApiId=REST_API_ID,
            stageName=self.current_live_api_domain['stage']
        )
        print("Deleted stage: "+self.current_demo_api_domain['stage'])
        # Recreate that stage based off most recent deployment
        vpc_link_response =self.api_client.get_vpc_links()
        for link in vpc_link_response['items']:
            if str(self.current_live_api_domain['stage']).upper() in str(link['name']).upper():
                self.current_live_api_domain['vpcLinkID']=link['id']

        create_stage_response = self.api_client.create_stage(
            restApiId=REST_API_ID,
            stageName=self.current_live_api_domain['stage'],
            deploymentId=deploy_response['id'],
            variables={
                'vpcLinkId': self.current_live_api_domain['vpcLinkID']
            })
        print("Created stage "+create_stage_response['stageName']+" connected to vpcLinkId "+create_stage_response['variables']['vpcLinkId'])
        # Set demo base path to demo color
        create_bpm_response = self.api_client.create_base_path_mapping(
            domainName=API_DEMO,
            basePath='(none)',
            restApiId=REST_API_ID,
            stage=create_stage_response['stageName']
        )
        print("Set "+API_DEMO+" to stage "+create_bpm_response['stage'])
        self.get_current_api_colors()

    def switch_base_path_mapping(self, domain):
        if domain['stage'] == 'blue':
            self.api_client.delete_base_path_mapping(domainName=domain['domainName'],
             basePath='(none)')
            self.api_client.create_base_path_mapping(domainName=domain['domainName'],
                                                    basePath='',
                                                    restApiId=REST_API_ID,
                                                    stage='green')
            print('Domain '+str(domain['domainName'])+' is now green')
            return 'green'
        elif domain['stage'] == 'green':
            self.api_client.delete_base_path_mapping(domainName=domain['domainName'],
             basePath='(none)')
            self.api_client.create_base_path_mapping(domainName=domain['domainName'],
                                                     basePath='',
                                                     restApiId=REST_API_ID,
                                                     stage='blue')
            print('Domain ' + str(domain['domainName']) + ' is now blue')
            return 'blue'
        else:
            print('Domain does not include stage: '+domain)


flipper = flip_blue_green()
flipper.flip_api_custom_domains()
flipper.flip_dashboard_route_53()
