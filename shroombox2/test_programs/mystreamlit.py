import streamlit as st
import json

# File path to store the slider value
json_file_path = "slider_value.json"

# Function to read the slider value from the JSON file
def read_slider_value():
    try:
        with open(json_file_path, "r") as json_file:
            data = json.load(json_file)
            return data.get("slider_value", 5)  # Default to 5 if the value is not found
    except (FileNotFoundError, json.JSONDecodeError):
        return 5  # Default to 5 if the file doesn't exist or is invalid JSON

# Function to write the slider value to the JSON file
def write_slider_value(value):
    with open(json_file_path, "w") as json_file:
        json.dump({"slider_value": value}, json_file)

# Initialize the slider value from the JSON file
current_slider_value = read_slider_value()

# Create an input box for entering a value
new_slider_value = st.text_input("Enter a new value:", current_slider_value)

try:
    write_slider_value(new_slider_value)  # Save the new value to the JSON file
    current_slider_value = new_slider_value  # Update the current value

except ValueError:
    st.warning("Please enter a valid integer value.")

# Display the current value from the JSON file
st.write(f'Updated Value from JSON: {current_slider_value}')

