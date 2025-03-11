import json
import random

from sdlabs_wrapper.wrapper import initialize_optimization

file_path = "data/config/conductivity_optimiser.json"
API_KEY = "eyJhbGciOiJIUzUxMiIsImtpZCI6ImtleV9lMmJiY2M4ZWVhMjU0MjU2ODVmZDUzMWE2ZTJmOTE1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2F1dGguYXRpbmFyeS5jb20iLCJjb2duaXRvOmdyb3VwcyI6WyJDQVBlWF9QaW9uZWVyX0NlbnRlciJdLCJpYXQiOjE3NDE3MTE4OTUsIm5iZiI6MTc0MTcxMTg5NSwidXNlcm5hbWUiOiJmMmM2ZDBiYy01OTQ1LTRiM2UtYjA3Mi0yMzc5ZTI1YmI0NjgifQ.caBOaBaSHE-IS-1zgcbGb7jzR05jry_X1i5gArasfSR_k5qy8BDx4tSDz8JTfCXMDMmVtjl4KoNU9LcDykk0HA"

# load config as dict
with open(file_path, "rb") as f:
    config_dict = json.load(f)
    
wrapper = initialize_optimization(
    api_key=API_KEY,
    spec_file_content=config_dict,
    inherit_data=False, 
    always_restart=True,
)

for iteration in range(wrapper.config.budget):
    print(f"Iteration {iteration+1}: Fetching new suggestions")
    suggestions = wrapper.get_new_suggestions(max_retries=10, sleep_time_s=30)

    print(f"Iteration {iteration+1} New Suggestions: {suggestions}")

    for suggestion in suggestions:
        print(suggestion.param_values)

        for obj in wrapper.config.objectives:
            suggestion.measurements[obj.name] = random.random()

    print(suggestion.measurements)

    if suggestions:
        wrapper.send_measurements(suggestions)
        print(f"Iteration {iteration+1} Measurements sent")