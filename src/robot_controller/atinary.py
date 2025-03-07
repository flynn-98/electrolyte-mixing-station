# import dependencies
import time
from pprint import pprint

import scientia_sdk as sct

# Configure API and authorization

API_KEY = "eyJhbGciOiJIUzUxMiIsImtpZCI6ImtleV8yOGY0OWNiNDkyNzI0MGJmYjQ4YzQ2MDRlYWY2YzI5ZCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2F1dGguYXRpbmFyeS5jb20iLCJjb2duaXRvOmdyb3VwcyI6WyJhY2FkZW1pYyJdLCJpYXQiOjE3NDEzNTEyODgsIm5iZiI6MTc0MTM1MTI4OCwidXNlcm5hbWUiOiJiYjc2MDk4My1mM2IwLTQ3YTEtOGY3Ny05ZGY0OGFiNjU1ODEifQ.wBEigYeKco5e9gYNT_b17VZRztwLw-no1ae8k3HpG96r06LPSFVIb73VkA1eg2AFjUs_T9vAumhFtXTOzfq5Wg"  # Add your API-KEY here
SDLABS_ENDPOINT_URL = "https://api.scientia.atinary.com/sdlabs/latest"  # as defined in API Endpoints

configuration = sct.Configuration(
    host = SDLABS_ENDPOINT_URL,
    api_key = {
        'api_key': API_KEY,
    }
)
configuration.access_token = None  # temporary fix when using the SDK

# Make an instance of the API client

# instance of ApiClient
sdlabs_api_client = sct.ApiClient(configuration)

# Create the necessary API objects
# manage workstations
wst_api = sct.WorkstationApi(sdlabs_api_client)

# manage parameters
prm_api = sct.ParameterApi(sdlabs_api_client)

# manage optimizers
opt_api = sct.OptimizerApi(sdlabs_api_client)

# manage objectives
obj_api = sct.ObjectiveApi(sdlabs_api_client)

# manage templates
tpl_api = sct.TemplateApi(sdlabs_api_client)

# manage campaigns
cpg_api = sct.CampaignApi(sdlabs_api_client)

# Select optimizer algorithm

WANTED_OPT = "Dragonfly"  # See 'Optimizers' page for a list of available optimizers
my_opt = next(opt for opt in opt_api.optimizers_list(is_public=True).objects if WANTED_OPT == opt.name)

print(my_opt)

# Select a workstation

WANTED_WST = "Dejong"  # See 'Surfaces' page for a list of available Workstations examples
my_wst = next(wst for wst in wst_api.workstations_list(is_public=True).objects if WANTED_WST == wst.name)

print(my_wst)

# Create template parameter space

param_a = prm_api.parameter_create(
    parameter_obj = sct.ParameterObj(
        name='param_a',
        description='parameter description',
        high_value=1.0,
        low_value=0.0,
        type='continuous',
    )
).object

param_b = prm_api.parameter_copy(
    param_a.id,
    parameter_copy=sct.ParameterCopy(name='param_b'),
).object

print(param_a)
print(param_b)

# Create the objective

my_objective = obj_api.objective_create(
    objective_obj=sct.ObjectiveObj(
        name='dejong', 
        description='2d continuous dejong surface', 
        goal=sct.Goal.MIN,  # can be MIN, MAX, TARGET (if "TARGET" goal is set, the argument "target" must be set with a numerical value)
    )
).object

print(my_objective)

# Create the template

my_tpl = tpl_api.template_create(
    template_obj=sct.TemplateObj(
        # budget: total number of objective function measurements allowed
        budget=5,
        # define optimizer
        optimizer=my_opt.id,
        # name of the optimization template
        name='dejong_template',
        # define the objective
        objective=my_objective.id,
        # define the parameters for each workstation
        parameters=[
            sct.StepObj(
                level=1,
                parameters=[
                    sct.ParameterCpgObj(
                        parameter_id=param_a.id,  # Copy of the workstation's parameter / parameters names should match!
                        workstation_id=my_wst.id,
                    ),
                    sct.ParameterCpgObj(
                        parameter_id=param_b.id,  # Copy of the workstation's parameter / parameters names should match!
                        workstation_id=my_wst.id,
                    ),
                ],
            )
        ],
    )
).object

print(my_tpl)

# Launch the template as a campaign

# create campaign
my_campaign = tpl_api.template_run(
    my_tpl.id,
    template_run_obj=sct.TemplateRunObj()
).object

print(my_campaign)

# wait until the campaign running is finished
running = True
while running:
    # Get campaign info
    cpg_status = next(
        tmp
        for tmp in cpg_api.campaigns_state(campaign_ids=[my_campaign.id]).objects[0].campaigns
        if tmp.id == my_campaign.id
    )

    if cpg_status.state in ['terminated', 'stopped']:
        running = False
    else:
        print(f'Campaign "{cpg_status.id}" with name "{cpg_status.name}" is running iteration {cpg_status.stats.running} out of {cpg_status.stats.budget}, status: {cpg_status.status.status}')

    # Checks campaign status.
    if cpg_status.status.status != 'ok':
        print(f'Campaign "{cpg_status.id}" with name "{cpg_status.name}" failed at iteration {cpg_status.stats.running} with ')
        cpg = cpg_api.campaign_get(campaign_id=my_campaign.id).object
        # formatting campaign events and errors:
        print(f'{", ".join(evt.type + ": " + evt.message + " (" + evt.date_time[:19] + ")" for evt in cpg.status.events)}.')

    time.sleep(5)

# print my campaign result
pprint(cpg_api.campaigns_results(campaign_ids=[my_campaign.id]))