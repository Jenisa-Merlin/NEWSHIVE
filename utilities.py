import configparser
import datetime
import re
from typing import List, Tuple

# Reads a configuration file and returns the config parser and section proxy
def get_configuration_file(file_name: str, section: str) -> tuple[configparser.ConfigParser, configparser.SectionProxy]:
	config = configparser.ConfigParser()
	config.read(file_name)
	configurations = config[section]
	return config, configurations

# Reads a specific configuration key from the configuration file
def read_configuration_file(config_key: str) -> str:
	_, configurations = get_configuration_file('configuration.ini', 'NEWS')
	return configurations.get(config_key, "")

# Saves a new value to the configuration file based on the key provided
def save_configuration_file(config_key: str, value: str) -> None:
	config, configurations = get_configuration_file('configuration.ini', 'NEWS')
	
	if config_key == "days_old":
		configurations[config_key] = str(value)
	else:
		old_value = configurations.get(config_key, "").replace('"', "")
		updated_value = f"{old_value}, {value}".strip(", ")
		configurations[config_key] = f'"{updated_value}"'
	
	with open('configuration.ini', 'w') as configfile:
		config.write(configfile)

# Checks if a domain is valid based on a regex pattern
def prepare_new_domains_to_add(message) -> Tuple[List[str], List[str]]:
	domain_list = [d.strip() for d in message.text.split(',')]

	domain_pattern = re.compile(r"^((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[A-Za-z]{2,})$")
	
	valid_domains = []
	invalid_domains = []

	for domain in domain_list:
		if domain_pattern.match(domain):
			print(f"yes the domain is correct {domain}")
			valid_domains.append(domain)
		else:
			print(f"the domain is not correct {domain}")
			invalid_domains.append(domain)
	
	return valid_domains, invalid_domains

# Get the current date and the date older than the configured number of days
def get_timeframe() -> Tuple[datetime.date, datetime.date]:
	days_old = int(read_configuration_file('days_old'))
	today = datetime.date.today()
	older_date = today - datetime.timedelta(days=days_old)
	return today, older_date