import yaml
from jinja2 import Environment, FileSystemLoader, Template

ENV = Environment(loader=FileSystemLoader('./'))

with open("device-vars.yml") as main_variables:
    main_variables =  yaml.load(main_variables)
with open("device-vars.yml") as main_variables_two:
    Devices = (yaml.load(main_variables_two))['Devices']
template = ENV.get_template("Baseline&Hardening_Configurations/Templates/Base&Hardening.template")
for DeviceName in Devices:
	if "IOSV" in DeviceName:
		with open("Baseline&Hardening_Configurations/{}.cfg".format(DeviceName), 'w') as config_output:
			config_template = template.render(main_variables, hostname=DeviceName, mgmt_ip=Devices[DeviceName]['mgmt_ip'], mgmt_mask=Devices[DeviceName]['mgmt_mask'])
			config_output.write(config_template)
		config_output.close()
	else:
		pass