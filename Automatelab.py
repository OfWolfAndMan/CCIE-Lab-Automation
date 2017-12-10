'''
Modified December 10, 2017

Version: 1.9

@author: OfWolfAndMan
'''

import sys
import os
import platform
import telnetlib
import time
import subprocess
import threading
from getpass import getpass
import netmiko
from netmiko import ConnectHandler
from tqdm import tqdm
import yaml
is_py2 = sys.version[0] == '2'
if is_py2:
    import Queue as queue
else:
    import queue as queue


def call_variables(stream):
	path = '/root/scripts/CCIE_Automation/'
	os.chdir(path)

	global localusername, localpassword, radiususer, radiuspass, scpuser, scppass, scpip

	localusername = stream['users']['localuser']['username']
	localpassword = stream['users']['localuser']['password']
	radiususer = stream['users']['radius']['username']
	radiuspass = stream['users']['radius']['password']
	scpuser = stream['users']['scp']['username']
	scppass = stream['users']['scp']['password']
	scpip = stream['nms']['scp']

"""Currently, this script is written for Cisco IOS. In the future, variants
may be written for other vendors' equipment."""

"""Default="yes" in the function below represents a default 
option. If the option is not specified otherwise, it resorts
to the default of "yes"."""
def query_yes_no(question, default="y"):
	"""Ask a yes/no question via raw_input() and return their answer.

	"question" is a string that is presented to the user.
	"default" is the presumed answer if the user just hits <Enter>.
		It must be "yes" (the default), "no" or None (meaning
		an answer is required of the user).

	The "answer" return value is True for "yes" or False for "no".
	"""
	global valid
	valid = {"y": True, "n": False}
	if default is None:
		prompt = " [y/n] "
	elif default == "y":
		prompt = " [Y/n] "
	elif default == "n":
		prompt = " [y/N] "
	else:
		raise ValueError("invalid default answer: '%s'" % default)
	while True:
		sys.stdout.write("{}{}".format(question, prompt))
		choice = raw_input().lower()
		if default is not None and choice == '':
			return valid[default]
		elif choice in valid:
			return valid[choice]
		else:
			sys.stdout.write("Please respond with 'y' or 'n' \n")

def install_premium_license(device_ip, device, DeviceName):
	print("""
			!#***************************************************************!#
			!# It is advised to take a snapshot after installing the premium !#
			!# license on each box in ESXi, as the trials are only limited   !#
			!# to so many days. Be sure to take your snapshots after running !#
			!# this script!                                                  !#
			!#***************************************************************!#
		  """)
	try:
		net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
		output = net_connect.send_command("\nconfigure terminal\nlicense boot level premium\nyes\nend\nwrite\nreload\n")
		net_connect.disconnect()
	except netmiko.ssh_exception.NetMikoTimeoutException:
		print("[!] Could not connect to device {}. Skipping...".format(DeviceName))
		pass
	except EOFError:
		pass
	pbar.update(100/float(len(Devices)))

def backup_config_single(device_ip, device, DeviceName):
	try:
		net_connect = ConnectHandler(device_type = device, ip = device_ip, username = localusername, password = localpassword)
		output = net_connect.send_command('copy running-config scp://root@192.168.15.188/Documents/backups/{}.txt\n\n\n\n{}\n'.format(DeviceName, scppass))
		net_connect.disconnect()
		successful_connections.append(DeviceName)
	except:
		unsuccessful_connections.append(DeviceName)

def exclude_devices():
	print("What devices would you like to exclude? Please choose a device based on its hostname\n")
	DeviceNames = []
	for DeviceName in Devices:
		print("[+] {} - {}".format(DeviceName, Devices[DeviceName]['mgmt_ip']))
		DeviceNames.append(DeviceName)
	print("[+] To finish your selections, type in 'done' when you are complete.")
	while True:
		try:
			exclude_device = raw_input()
			if exclude_device == "done":
				break
			elif exclude_device not in DeviceNames:
				print("[!] Invalid entry. Please make sure you are entering a valid hostname.")
				continue
			else:
				del Devices[exclude_device]
				print("[+] Excluded device {} from task.".format(exclude_device))
		except KeyError:
			print("[!] That device has already been excluded.")
			continue


def default_configurations():
	device = 'cisco_ios'
	print("[+] Initiating startup configuration wipe of all applicable devices\n")
	for DeviceName in Devices:
		device_ip = Devices[DeviceName]['mgmt_ip']
		try:
			net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
			output = net_connect.send_command_expect("\nend\nwrite memory\nwrite erase\n\nreload\n\n")
			net_connect.disconnect()
			print("[+] Configuration wiped successfully for device {}".format(DeviceName))
			time.sleep(5)
		except netmiko.ssh_exception.NetMikoTimeoutException:
			print("[!] Could not connect to device {}. Skipping...".format(DeviceName))
			continue
		except:
			pass

def ping_em_all(device_ip, DeviceName, pingable_devices, unpingable_devices, limbo):
	""".rstrip is needed for the ip as .readline adds a \n to
	the lines' text"""
	if "Linux" in platform.system():
		ping_reply = subprocess.Popen(['ping', '-c', '2', '-w', '2', '-q', device_ip.rstrip('\n')],stdout=limbo, stderr=limbo).wait()
	#Darwin is Mac OSX
	elif "Darwin" in platform.system():
		ping_reply = subprocess.Popen(['ping', '-c', '2', '-t', '2', '-q', '-n', device_ip.rstrip('\n')],stdout=limbo, stderr=limbo).wait()
		"""Subprocess for Cygwin still not supported"""
	else:
	#Only other would be Windows
		ping_reply = subprocess.Popen(['ping', '-n', '2', '-w', '2', device_ip.rstrip('\n')],stdout=limbo, stderr=limbo).wait()
	if ping_reply == 0:
		pingable_devices[DeviceName] = device_ip
	elif ping_reply == 2:
		unpingable_devices[DeviceName] = device_ip
	else:
		unpingable_devices[DeviceName] = device_ip

def ip_reachability_group():
	print("\n[+] Checking IP reachability. Please wait...")
	pingable_devices = {}
	global unpingable_devices
	unpingable_devices = {}
	with open(os.devnull, "wb") as limbo:
		#print("\n[+] Progress:\n")
		my_args = (pingable_devices, unpingable_devices, limbo)
		my_target = ping_em_all
		create_some_threads(my_target, *my_args)
	print("")
	print("[!] Removing devices...")
	for rdevice in unpingable_devices:
		del Devices[rdevice]
	print("\n[!] Removed from future tasks:")
	print("*" * 30)
	for unreach in unpingable_devices:
		print("| [-] {} - {}".format(unreach, unpingable_devices[unreach]))
	print("*" * 30)
	print("\n[+] Devices remaining:")
	print("{}".format("*" * 30))
	for DeviceName in Devices:
		print("| [+] {} - {}".format(DeviceName,Devices[DeviceName]['mgmt_ip']))
	print("*" * 30)
def get_bgp_asn(device_ip, DeviceName, output_q):
	output_dict = {}
	device = 'cisco_ios'
	net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
	output = net_connect.send_command("show run | inc router bgp\n")
	if "bgp" in output:
		newoutput = output.replace("router bgp ", "")
	else:
		newoutput = "N/A"
	output = "| ASN for device {}: {}{}|".format(DeviceName, newoutput, " " * (7 - len(DeviceName)))
	net_connect.disconnect()
	output_dict[DeviceName] = output
	output_q.put(output_dict)

def backup_config():
	global unsuccessful_connections
	unsuccessful_connections = []
	global successful_connections
	successful_connections = []
	print("[+] Initiating device backup procedure.")
	for DeviceName in Devices:
		global device_ip
		device_ip = Devices[DeviceName]['mgmt_ip']
		device = 'cisco_ios'
		try:
			net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
			output = net_connect.send_command('copy running-config scp://root@{}/Documents/backups/{}.txt\n\n\n\n{}\n'.format(scpip, DeviceName, scppass))
			net_connect.disconnect()
			successful_connections.append(DeviceName)
		except:
			print("[+] Could not SSH to device {}. Trying serial connection...".format(DeviceName))
			telnet_attempt(DeviceName)
			backup_config_single(device_ip, device, DeviceName)
	print("")
	print("Successful backups:")
	for yz in successful_connections:
		print("[+] {}".format(yz))
	print("")
	print("Unsuccessful backups:")
	for xy in unsuccessful_connections:
		print("[-] {}".format(xy))
	print("")

def telnet_initial(device_ip, DeviceName, domainname, localusername, localpassword):
	try:
		print("[+] Attempting Out-of-Band IP configuration of device {}...".format(DeviceName))
		serialip = Devices[DeviceName]['serial_ip']
		port = Devices[DeviceName]['serial_port']
		#Specify the connection timeout in seconds for blocking operations, like the connection attempt
		connection_timeout = 5
		reading_timeout = 5
		if port != '23':
			cmd_ser1 = '\xff\xfc\x25'
			cmd_ser2 = '\xff\xfb\x00'
			cmd_ser3 = '\xff\xfd\x00\xff\xfb\x03\xff\xfd \x03\xff\xfd\x01\xff\xfe\xe8'
			cmd_ser4 = '\xff\xfe\x2c'
			connection = telnetlib.Telnet(serialip, port, connection_timeout)
			#connection.set_debuglevel(100)
			connection.write(cmd_ser1)
			time.sleep(1)
			connection.write(cmd_ser2)
			time.sleep(1)
			connection.write(cmd_ser3)
			time.sleep(1)
			connection.write(cmd_ser4)
			time.sleep(1)
		else:
			port = '23'
			connection = telnetlib.Telnet(serialip, port, connection_timeout)
		#Waiting to be asked for a username
		#Serial over telnet requires carriage return
		connection.write("\r\n")
		time.sleep(2)
		#connection.write("no\r\n\r\n")
		#time.sleep(20)
		router_output = connection.read_until(">", reading_timeout)
		connection.write("enable\r\n")
		connection.write("configure terminal\r\n")
		router_output = connection.read_until("(config)#", reading_timeout)
		time.sleep(1)
		connection.write("hostname %s\r\n" % DeviceName)
		connection.write("ip domain-name %s\r\n" % domainname)
		connection.write("crypto key generate rsa general-keys modulus 2048\r\n")
		time.sleep(3)
		connection.write("interface Gig2\r\n")
		connection.write("ip address %s 255.255.255.224\r\n" % device_ip)
		connection.write("no shutdown\r\n")
		time.sleep(1)
		connection.write("enable secret %s\r\n" % localpassword)
		connection.write("ip route 0.0.0.0 0.0.0.0 10.51.60.33 2\n")
		#The reason there is an AD of 2 for the default route is due to having them in 
		#the lab scenarios sometimes.
		connection.write("username %s privilege 15 secret %s\r\n" % (localusername, localpassword) )
		connection.write("line vty 0 4\r\n")
		connection.write("login local\r\n")
		connection.write("transport input ssh\r\n")
		connection.write("end\r\n")
		connection.write("write memory\r\n")
		time.sleep(2)
		print("[+]Resolving ARP entry for device %s." % DeviceName)
		connection.write("ping 208.67.222.222\n")
		time.sleep(3)
		print("[+]In-band interface configuration successful for device %s." % DeviceName)
		connection.read_very_eager()
		connection.close()
		time.sleep(5)
	except:
		print("[!] Serial over telnet attempt failed for device %s." % DeviceName)


def telnet_attempt(DeviceName):
	try:
		print("[+] Attempting Out-of-Band IP configuration of device...")
		#Define telnet parameters
		#Specify the Telnet port (default is 23, anyway)
		serialip = Devices[DeviceName]['serial_ip']
		port = Devices[DeviceName]['serial_port']
		#Specify the connection timeout in seconds for blocking operations, like the connection attempt
		connection_timeout = 5
		#Specify a timeout in seconds. Read until the string is found or until the timout has passed
		reading_timeout = 5		
		#Logging into device
		connection = telnetlib.Telnet(serialip, port, connection_timeout)
		#Waiting to be asked for an username
		connection.write("\n")
		time.sleep(1)
		router_output = connection.read_until("Username:", reading_timeout)
		#Enter the username when asked and a "\n" for Enter
		connection.write(localusername + "\n")

		#Waiting to be asked for a password
		router_output = connection.read_until("Password:", reading_timeout)
		#Enter the password when asked and a "\n" for Enter
		connection.write("{}\n".format(localpassword))
		time.sleep(30)
		#Entering global config mode
		connection.write("end\n")
		time.sleep(1)
		connection.write("configure terminal\n")
		time.sleep(1)
		connection.write("interface Gig2\n")
		time.sleep(1)
		connection.write("ip address {} 255.255.255.224\n".format(device_ip))
		connection.write("no shutdown\n")
		time.sleep(1)
		connection.write("interface Gig2\n")
		connection.write("no shutdown\n")
		time.sleep(5)
		print("[+]In-band interface configuration successful for device {}. Trying SSH connection again.".format(DeviceName))
		connection.close()
		time.sleep(20)
	except:
		print("[!] Serial over telnet attempt failed for device {}.".format(DeviceName))
		unsuccessful_connections.append(DeviceName)

def reinitialize_basehardening():
	from napalm import get_network_driver
	while True:
		localorradius = raw_input("[?] Are you currently using RADIUS or local credentials? [local/radius]\n")
		if localorradius == 'local':
			username = localusername
			password = localpassword
			break
		elif localorradius == 'radius':
			username = radiususer
			password = radiuspass
			break
		else:
			print("[!] Invalid input. Please try again.\n")
			continue
	print("[+] Copying baseline and hardening scripts to devices.\n")
	print("\n[+] Progress\n")
	pbar = tqdm(total=100)
	driver = get_network_driver('ios')
	for DeviceName in Devices:
		device_ip = Devices[DeviceName]['mgmt_ip']
		optional_args = {'global_delay_factor': 3}
		device = driver(device_ip, username, password, optional_args=optional_args)
		device.open()
		device.load_replace_candidate(filename='Baseline&Hardening_Configurations/Builds/{}.cfg'.format(DeviceName))
		device.commit_config()
		device.close()
		pbar.update(100/len(Devices))
	pbar.close()
	print("[+] All configurations have been converted to the bare baseline/hardening templates successfully.\n")
def choose_scenario_type():
	while True:
		RandS = raw_input('[?] Are these configurations for a switching lab, a routing lab, or both? Choose one of the three options: [sw/rt/both]')
		if RandS == 'rt':
			Switching_Devices = []
			for DeviceName in Devices:
				if 'IOSV' not in DeviceName:
					Switching_Devices.append(DeviceName)
				else:
					pass

			for Switch in Switching_Devices:
				del Devices[Switch]
			break
		elif RandS == 'sw':
			Routing_Devices = []
			for DeviceName in Devices:
				if 'SW' not in DeviceName:
					Routing_Devices.append(DeviceName)
				else:
					pass

			for Router in Routing_Devices:
				del Devices[Router]
			break
		elif RandS == 'both':
			break
		else:
			print("[!] Invalid input. Please try again!\n")
			continue
def scenario_configuration_threading():
#Purpose: Deploys a scenario configuration for a lab workbook. Currently, only INE's lab workbook is applicable,
#but this may change in the future.
	#sys.setdefaultencoding('utf-8')
	path = '/root/scripts/CCIE_Automation/Scenario_Configurations/ine.ccie.rsv5.workbook.initial.configs/advanced.technology.labs'
	os.chdir(path)
	print("[+] Which Baseline Configs would you like to implement?\n")
	dir_output = []
	for dir in enumerate(sorted(os.listdir('.')), start = 1):
		#print "[+] %d %s" % (ij, dir)
		dir_output.append(dir)
		#dir_output[ij] = dir
	#Using the below, I was able to print the options in three columns
	for a,b,c in zip(dir_output[::3],dir_output[1::3],dir_output[2::3]):
		print("{:<47}{:<55}{:25}".format(a,b,c))
	while True:
		option = raw_input("[+] Choose an option by integer.\n")
		if int(option) > len(dir_output):
			print("[!] You chose an incorrect value. Try again.\n")
			continue
		else:
			for x,y in dir_output:
				if x == int(option):
					initial_config_folder = y
					final_path = os.chdir(initial_config_folder)
			print("[+] Pushing scenario configurations to all devices.")
			#my_args = {"arg": "placeholder"}
			my_target = scenario_configuration_install
			create_some_threads(my_target)
		break

def create_some_threads(my_target, *my_args, **my_keyword_args):
	for DeviceName in Devices:
		device_ip = Devices[DeviceName]['mgmt_ip']
		my_args = (device_ip, DeviceName,) + my_args
		#my_keyword_args = {device_ip: Devices[DeviceName]['mgmt_ip'], DeviceName: DeviceName}
		my_thread = threading.Thread(target=my_target, args=my_args, kwargs=my_keyword_args)
		my_thread.start()
		# Wait for all threads to complete
		my_args_list = list(my_args)
		my_args_list.remove(device_ip)
		my_args_list.remove(DeviceName)
		my_args = tuple(my_args_list)
	main_thread = threading.currentThread()
	for some_thread in threading.enumerate():
		if some_thread != main_thread:
			some_thread.join()

def scenario_configuration_install(device_ip, DeviceName):
	selected_cmd_file = open('{}.txt'.format(DeviceName), 'rb')
	command_set = []
	selected_cmd_file.seek(0)
	device = 'cisco_ios'
	for each_line in selected_cmd_file.readlines():
		if '\r' not in each_line:
			each_line = each_line.strip('\n')
			each_line = ("{}\r\n".format(each_line))
			command_set.append(each_line)
		else:
			command_set.append(each_line)
	try:
		net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
		output = net_connect.send_config_set(command_set)
		net_connect.disconnect()
	except netmiko.ssh_exception.NetMikoTimeoutException:
		pass
	print("[+] Scenario configuration of device {} successful.".format(DeviceName))
	selected_cmd_file.close()

def render_templates():
	from jinja2 import Environment, FileSystemLoader, Template
	ENV = Environment(loader=FileSystemLoader('./'))

	with open("device-vars.yml") as main_variables:
		main_variables = yaml.load(main_variables)
	with open("device-vars.yml") as main_variables_two:
	    Devices = (yaml.load(main_variables_two))['Devices']
	template = ENV.get_template("Baseline&Hardening_Configurations/Templates/Base&Hardening.template")
	for DeviceName in Devices:
		if "IOSV" in DeviceName:
			with open("Baseline&Hardening_Configurations/Builds/{}.cfg".format(DeviceName), 'w') as config_output:
				config_template = template.render(main_variables, hostname=DeviceName, mgmt_ip=Devices[DeviceName]['mgmt_ip'], mgmt_mask=Devices[DeviceName]['mgmt_mask'])
				config_output.write(config_template)
			config_output.close()
		else:
			pass
def get_the_facts():
	while True:
		localorradius = raw_input("[?] Are you currently using RADIUS or local credentials? [local/radius]\n")
		if localorradius == 'local':
			username = localusername
			password = localpassword
			break
		elif localorradius == 'radius':
			username = radiususer
			password = radiuspass
			break
		else:
			print("[!] Invalid input. Please try again.\n")
			continue
	driver = get_network_driver('ios')
	fact_list = {}
	for DeviceName in Devices:
		device_ip = Devices[DeviceName]['mgmt_ip']
		optional_args = {'global_delay_factor': 3}
		device = driver(device_ip, username, password, optional_args=optional_args)
		device.open()
		facts = device.get_facts()
		device.close()
		fact_list[DeviceName]=facts
	print("[+] Done gathering all teh facts! See below.")
	for key, value in fact_list.iteritems():
		print(key + ": " + value)


def main_menu_selection():
	try:
		print("""
			!#********************************************************************!#
			!#                                                                    !#
			!#   Welcome to the CCIE Automation script! The purpose of this       !#
			!#   script is to streamline your CSR1000v/IOSv deployment,           !#
			!#   as well as the physical switches in your environment. Be sure.   !#
			!#   to appropriately define your variables in the device-vars.yml.   !#
			!#   file before proceeding. Please use the example file in this      !#
			!#   program's local directory.                                       !#
			!#                                                                    !#
			!#********************************************************************!#
		  """)
		in_place = query_yes_no("[?] Do you already have the yaml file setup properly?")
		if in_place == True:
			pass
		else:
			sys.exit("[!] You need to configure your yaml file before proceeding.")
		main_menu = {}
		main_menu['1']="Establish basic connectivity to the boxes"
		main_menu['2']="Convert running configurations to baseline/hardening templates"
		main_menu['3']="Enable premium license (Note: This MUST be enabled for certain scenario configurations!)"
		main_menu['4']="Push Scenario Configurations (INE)"
		main_menu['5']="Run configuration Backup"
		main_menu['6']="Get BGP ASNs for all routers"
		main_menu['7']="Wipe device configurations and start from scratch"
		main_menu['8']="Get device facts"
		main_menu['9']="Exit"
		while True:
			options=main_menu.keys()
			options.sort(key=int)
			print("!#{}!#".format("*" * 95))
			print("!#{}!#".format(" " * 95))
			menu_num = 1
			for entry in options:
				print("!# [+]{} {}{}!#".format(entry, main_menu[entry], " " * (90 - len(main_menu[entry]) - len(str(menu_num)))))
				menu_num += 1
			print("!#{}!#".format(" " * 95))
			print("!#{}!#".format("*" * 95))
			print("")
			selection=raw_input("[*] Please select the option you'd like to run:\n")
			if selection == '1':
				domainname = raw_input("[?] What is your FQDN?\n")
				my_args = (domainname, localusername, localpassword)
				my_target = telnet_initial
				create_some_threads(my_target, *my_args)
			elif selection == '2':
				time_before = time.time()
				choose_scenario_type()
				templates_created = query_yes_no("[?] Have the templates already been created?")
				if templates_created == False:
					print("[!] Rendering templates...")
					render_templates()
					print("[+] Done.")
				else:
					pass
				print("[+] Applying templates...")
				reinitialize_basehardening()
				time_after = time.time()
				print("[+] Total time to completion: {} seconds".format(round(time_after - time_before, 2)))
				print("")
			elif selection == '3':
				device = 'cisco_ios'
				pbar = tqdm(total=100)
				for DeviceName in Devices:
					device_ip = Devices[DeviceName]['mgmt_ip']
					print("\n[+] Progress:\n")
					install_premium_license(device_ip, device, DeviceName)
				pbar.close()
			elif selection == '4':
				time_before = time.time()
				choose_scenario_type()
				exclude = query_yes_no("[?] Would you like to exclude any additional devices prior to pushing scenario configs?", default="n")
				if exclude == False:
					pass
				else:
					exclude_devices()
				scenario_configuration_threading()
				time_after = time.time()
				print("[+] Total time to completion: {} seconds".format(round(time_after - time_before, 2)))
				print("")
				raw_input("[+] Press enter to return to the main menu\n")
			elif selection == '5':
				"""The Linux SCP server used in this script is natively installed. One issue you 
				may encounter is an issue with one of your switches or routers not having a cipher
				supported by the SCP server. To change this, you will need to edit your ssh configuration
				in the /etc/ssh/sshd_config file"""
				exclude = query_yes_no("[?] Would you like to exclude any devices from your backup?", default="n")
				if exclude == False:
					pass
				else:
					exclude_devices()
				backup_config()
			elif selection == '6':
				print("[+] Getting BGP ASNs for all routers...")
				time_before = time.time()
				print("\n" + "=" * 30)
				output_q = Queue()
				for DeviceName, value in Devices.items():
					if value["device_type"] == "router":
						device_ip = Devices[DeviceName]['mgmt_ip']
						my_thread = threading.Thread(target=get_bgp_asn, args=(device_ip, DeviceName, output_q))
						my_thread.start()
					else:
						pass
	    		# Wait for all threads to complete
				main_thread = threading.currentThread()
				for some_thread in threading.enumerate():
					if some_thread != main_thread:
						some_thread.join()

    			# Retrieve everything off the queue
				while not output_q.empty():
					my_dict = output_q.get()
					for k, val in my_dict.iteritems():
						print(val)
				print(("=" * 30) + "\n")
				print("[+] Done")
				time_after = time.time()
				print("[+] Total time to completion: {} seconds".format(round(time_after - time_before, 2)))
				raw_input("[+] Press enter to return to the main menu\n")
			elif selection == '7':
				exclude = query_yes_no("[?] Would you like to exclude any devices from your config wipe?", default="n")
				if exclude == False:
					pass
				else:
					exclude_devices()
				default_configurations()
			elif selection == '8':
				get_the_facts()
			elif selection == '9':
				print("Bye")
				break
			else:
				print("[!] Invalid option. Please try again.\n")
	except KeyboardInterrupt:
		print("\n[!] Keyboard Interrupt detected. Goodbye!")
		sys.exit()

if __name__ == "__main__":
	stream = open('device-vars.yml', 'r')
	stream = yaml.load(stream)
	Devices = stream['Devices']
	print("[!] Need to check IP reachability and removable any unreachable devices first. Please wait...")
	ip_reachability_group()
	in_place = query_yes_no("\nDevices that are reachable are listed above. Proceed?")
	if in_place == True:
			pass
	else:
		sys.exit("Exiting!")
	call_variables(stream)
	main_menu_selection()
