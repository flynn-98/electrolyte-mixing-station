import json
import random

from sdlabs_wrapper.wrapper import initialize_optimization

file_path = "data/config/example.json"
API_KEY = "eyJhbGciOiJIUzUxMiIsImtpZCI6ImtleV8yOGY0OWNiNDkyNzI0MGJmYjQ4YzQ2MDRlYWY2YzI5ZCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2F1dGguYXRpbmFyeS5jb20iLCJjb2duaXRvOmdyb3VwcyI6WyJhY2FkZW1pYyJdLCJpYXQiOjE3NDEzNTEyODgsIm5iZiI6MTc0MTM1MTI4OCwidXNlcm5hbWUiOiJiYjc2MDk4My1mM2IwLTQ3YTEtOGY3Ny05ZGY0OGFiNjU1ODEifQ.wBEigYeKco5e9gYNT_b17VZRztwLw-no1ae8k3HpG96r06LPSFVIb73VkA1eg2AFjUs_T9vAumhFtXTOzfq5Wg"

# load config as dict
with open(file_path, "rb") as f:
    config_dict = json.load(f)
wrapper = initialize_optimization(
    api_key=API_KEY,
    spec_file_content=config_dict,
    inherit_data=False, 
)

for iteration in range(wrapper.config.budget):
    print(f"Iteration {iteration+1}: Fetching new suggestions")
    suggestions = wrapper.get_new_suggestions(max_retries=6, sleep_time_s=60)

    print(f"Iteration {iteration+1} New Suggestions: {suggestions}")

    for suggestion in suggestions:
        for obj in wrapper.config.objectives:
            suggestion.measurements[obj.name] = random.random()

    if suggestions:
        wrapper.send_measurements(suggestions)
        print(f"Iteration {iteration+1} Measurements sent")