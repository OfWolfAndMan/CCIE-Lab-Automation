'''
Modified September 24, 2017

Version: 1.3

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
from napalm import get_network_driver

Devices = {'SW4': ['192.168.10.105'], 'IOSV1': ['10.51.60.36', '192.168.10.120', '2001'],
		   'IOSV2': ['10.51.60.37', '192.168.10.120', '2002'], 'IOSV3': ['10.51.60.38', '192.168.10.120', '2003'],
		   'IOSV4': ['10.51.60.39', '192.168.10.120', '2004'], 'IOSV5': ['10.51.60.40', '192.168.10.120', '2005'],
		   'IOSV6': ['10.51.60.41', '192.168.10.120', '2006'], 'IOSV7': ['10.51.60.42', '192.168.10.120', '2007'],
		   'IOSV8': ['10.51.60.43', '192.168.10.120', '2008'], 'IOSV9': ['10.51.60.44', '192.168.10.120', '2009'],
		   'IOSV10': ['10.51.60.45', '192.168.10.120', '2010'], 'SW1': ['192.168.10.102'],
		   'SW2': ['192.168.10.103'], 'SW3': ['192.168.10.104']
		   }

def call_variables():
	path = '/root/scripts/CCIE_Automation/'
	os.chdir(path)

	global localusername, localpassword, radiususer, radiuspass, scpuser, scppass, scpip
	variables = []
	variable_file_one = open('userlist.txt', 'r')
	variable_file_one.seek(0)
	for eachline in variable_file_one.readlines():
		variables.append(eachline.rstrip())
	variable_file_one.close()
	variable_file_two = open('netserver.txt', 'r')
	variable_file_two.seek(0)
	for eachline in variable_file_two.readlines():
		variables.append(eachline.rstrip())
	variable_file_two.close()

	localusername = variables[0]
	localpassword = variables[1]
	radiususer = variables[2]
	radiuspass = variables[3]
	scpuser = variables[4]
	scppass = variables[5]
	scpip = variables[6]

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
		sys.stdout.write(question + prompt)
		choice = raw_input().lower()
		if default is not None and choice == '':
			return valid[default]
		elif choice in valid:
			return valid[choice]
		else:
			sys.stdout.write("Please respond with 'y' or 'n' \n")

def install_premium_license(device_ip, device, DeviceName):
	print """
			!#***************************************************************!#
			!# It is advised to take a snapshot after installing the premium !#
			!# license on each box in ESXi, as the trials are only limited   !#
			!# to so many days. Be sure to take your snapshots after running !#
			!# this script!                                                  !#
			!#***************************************************************!#
		  """
	try:
		net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
		output = net_connect.send_command("\nconfigure terminal\nlicense boot level premium\nyes\nend\nwrite\nreload\n")
		net_connect.disconnect()
	except netmiko.ssh_exception.NetMikoTimeoutException:
		print "[!] Could not connect to device %s. Skipping..." % DeviceName
		pass
	except EOFError:
		pass
	pbar.update(100/float(len(Devices)))

def backup_config_single(device_ip, device, DeviceName):
	try:
		net_connect = ConnectHandler(device_type = device, ip = device_ip, username = localusername, password = localpassword)
		output = net_connect.send_command('copy running-config scp://root@192.168.15.188/Documents/backups/%s.txt\n\n\n\n%s\n' % (DeviceName, scppass))
		net_connect.disconnect()
		successful_connections.append(DeviceName)
	except:
		unsuccessful_connections.append(DeviceName)

def exclude_devices():
	print "What devices would you like to exclude? Please choose a device based on its hostname\n"
	DeviceNames = []
	for DeviceName in Devices:
		print "{+} ", DeviceName, "- ",	 Devices[DeviceName][0]
		DeviceNames.append(DeviceName)
	print "[+] To finish your selections, type in 'done' when you are complete."
	while True:
		try:
			exclude_device = raw_input()
			if exclude_device == "done":
				break
			elif exclude_device not in DeviceNames:
				print "[!] Invalid entry. Please make sure you are entering a valid hostname."
				continue
			else:
				del Devices[exclude_device]
				print "[+] Excluded device %s from task." % exclude_device
		except KeyError:
			print "[!] That device has already been excluded."
			continue

def create_threads(domainname, localuser, localpass):
        threads = []
        for DeviceName in Devices:
                th = threading.Thread(target = telnet_initial, args = (domainname, localusername, localpassword, DeviceName))
                th.start()
                threads.append(th)

                for th in threads:
                        th.join()


def default_configurations():
	device = 'cisco_ios'
	print "[+] Initiating startup configuration wipe of all applicable devices\n"
	for DeviceName in Devices:
		device_ip = Devices[DeviceName][0]
		try:
			net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
			output = net_connect.send_command_expect("\nend\nwrite memory\nwrite erase\n\nreload\n\n")
			net_connect.disconnect()
			print "[+] Configuration wiped successfully for device %s" % DeviceName
			time.sleep(5)
		except netmiko.ssh_exception.NetMikoTimeoutException:
			print "[!] Could not connect to device %s. Skipping..." % DeviceName
			continue
		except:
			pass

def ip_reachability_group():
	print "\n[+] Checking IP reachability. Please wait...\n"
	pingable_devices = {}
	global unpingable_devices
	unpingable_devices = {}
	with open(os.devnull, "wb") as limbo:
		print "\n[+] Progress:\n"
		pbar = tqdm(total=100)
		for DeviceName in Devices:
			device_ip = Devices[DeviceName][0]
			""".rstrip is needed for the ip as .readline adds a \n to
			the lines' text"""
			if "Linux" in platform.system():
				ping_reply = subprocess.Popen(['ping', '-c', '2', '-w', '2', '-q', device_ip.rstrip('\n')],stdout=limbo, stderr=limbo).wait()
			#Darwin is Mac OSX
			elif "darwin" in platform.system():
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
			pbar.update(100/float(len(Devices)))
		pbar.close()
	print "[+]The following devices were reachable:\n"
	for reach in pingable_devices:
		print "{+} ", reach,"- ", pingable_devices[reach]
	print ""
	print "[!]The following devices were unreachable:\n"
	for unreach in unpingable_devices:
		print "{-} ", unreach,"- ", unpingable_devices[unreach]
	print ""
	remove_devices = query_yes_no("[?] Would you like to remove the devices that are unpingable from your tasks for now?")
	if remove_devices == False:
		pass
	else:
		for rdevice in unpingable_devices:
			del Devices[rdevice]
		print "[+] Devices removed for the remainder of your tasks."
		print "[+] Devices remaining:"
		for DeviceName in Devices:
			print "{+}", DeviceName,"- ", Devices[DeviceName][0]

def get_bgp_asn():
	device = 'cisco_ios'
	for DeviceName in Devices:
		if "CSR1000V" in DeviceName:
			device_ip = Devices[DeviceName][0]
			net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
			output = net_connect.send_command("show run | inc router bgp\n")
			if "bgp" in output:
				newoutput = output.replace("router bgp ", "")
			else:
				newoutput = "N/A"
			print "ASN for device %s: %s" % (DeviceName, newoutput)
			net_connect.disconnect()
		else:
			pass
	print "Done"

def backup_config():
	global unsuccessful_connections
	unsuccessful_connections = []
	global successful_connections
	successful_connections = []
	print "[+] Initiating device backup procedure."
	global DeviceName
	for DeviceName in Devices:
		global device_ip
		device_ip = Devices[DeviceName][0]
		device = 'cisco_ios'
		try:
			net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
			output = net_connect.send_command('copy running-config scp://root@%s/Documents/backups/%s.txt\n\n\n\n%s\n' % (scpip, DeviceName, scppass))
			net_connect.disconnect()
			successful_connections.append(DeviceName)
		except:
			print '[+] Could not SSH to device %s. Trying serial connection...' % DeviceName
			telnet_attempt()
			backup_config_single(device_ip, device, DeviceName)
	print ""
	print "Successful backups:"
	for yz in successful_connections:
		print yz
	print ""
	print "Unsuccessful backups:"
	for xy in unsuccessful_connections:
		print xy
	print ""

def telnet_initial(domainname, localusername, localpassword, DeviceName):
	try:
		device_ip = Devices[DeviceName][0]
		print "[+] Attempting Out-of-Band IP configuration of device %s..." % DeviceName
		serialip = Devices[DeviceName][1]
		port = Devices[DeviceName][2]
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
		print "[+]Resolving ARP entry for device %s." % DeviceName
		connection.write("ping 208.67.222.222\n")
		time.sleep(3)
		print '[+]In-band interface configuration successful for device %s.' % DeviceName
		connection.read_very_eager()
		connection.close()
		time.sleep(5)
	except:
		print "[!] Serial over telnet attempt failed for device %s." % DeviceName


def telnet_attempt():
	try:
		print "[+] Attempting Out-of-Band IP configuration of device..."
		#Define telnet parameters
		#Specify the Telnet port (default is 23, anyway)
		serialip = Devices[DeviceName][1]
		port = Devices[DeviceName][2]
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
		connection.write(localpassword + "\n")
		time.sleep(30)
		#Entering global config mode
		connection.write("end\n")
		time.sleep(1)
		connection.write("configure terminal\n")
		time.sleep(1)
		connection.write("interface Gig2\n")
		time.sleep(1)
		connection.write("ip address %s 255.255.255.224\n" % device_ip)
		connection.write("no shutdown\n")
		time.sleep(1)
		connection.write("interface Gig2\n")
		connection.write("no shutdown\n")
		time.sleep(5)
		print '[+]In-band interface configuration successful for device %s. Trying SSH connection again.' % DeviceName
		connection.close()
		time.sleep(20)
	except:
		print "[!] Serial over telnet attempt failed for device {}.".format(DeviceName)
		unsuccessful_connections.append(DeviceName)

def reinitialize_basehardening():
	device = 'cisco_ios'
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
			print "[!] Invalid input. Please try again.\n"
			continue
	print "[+] Copying baseline and hardening scripts to devices.\n"
	print "\n[+] Progress\n"
	pbar = tqdm(total=100)
        driver = get_network_driver('ios')
	for DeviceName in Devices:
		device_ip = Devices[DeviceName][0]
		optional_args = {'global_delay_factor': 3}
		device = driver(device_ip, username, password, optional_args=optional_args)
		device.open()
		device.load_replace_candidate(filename='Baseline&Hardening_Configurations/Base&Hardening_{}.txt'.format(DeviceName))
		device.commit_config()
		device.close()
		pbar.update(100/len(Devices))
	pbar.close()
	print "[+] All configurations have been converted to the bare baseline/hardening templates successfully.\n"
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
			print "[!] Invalid input. Please try again!\n"
			continue
def scenario_configuration():
#Purpose: Deploys a scenario configuration for a lab workbook. Currently, only INE's lab workbook is applicable,
#but this may change in the future.
	path = '/root/scripts/CCIE_Automation/Scenario_Configurations/ine.ccie.rsv5.workbook.initial.configs/advanced.technology.labs'
	os.chdir(path)
	print "[+] Which Baseline Configs would you like to implement?\n"
	dir_output = []
	for dir in enumerate(os.listdir('.'), start = 1):
		#print "[+] %d %s" % (ij, dir)
		dir_output.append(dir)
		#dir_output[ij] = dir
	#Using the below, I was able to print the options in three columns
	for a,b,c in zip(dir_output[::3],dir_output[1::3],dir_output[2::3]):
		print '{:<50}{:<43}{:<}'.format(a,b,c)
	while True:
		option = raw_input("[+] Choose an option by integer.\n")
		if int(option) > len(dir_output):
			print "[!] You chose an incorrect value. Try again.\n"
			continue
		else:
			for x,y in dir_output:
				if x == int(option):
					initial_config_folder = y
					final_path = os.chdir(initial_config_folder)
			device = 'cisco_ios'
			for DeviceName in Devices:
				device_ip = Devices[DeviceName][0]
				selected_cmd_file = open('%s.txt' % DeviceName, 'r')
				print "[+] Pushing scenario configuration for device %s." % DeviceName
				command_set = []
				selected_cmd_file.seek(0)
				for each_line in selected_cmd_file.readlines():
					command_set.append(each_line)
				try:
					net_connect = ConnectHandler(device_type = device, ip = device_ip, username = radiususer, password = radiuspass)
					output = net_connect.send_config_set(command_set)
					net_connect.disconnect()
				except netmiko.ssh_exception.NetMikoTimeoutException:
					pass
				print "[+] Scenario configuration of device %s successful.\n" % DeviceName
				selected_cmd_file.close()
		break


def main_menu_selection():
	try:
		print("""
			!#*****************************************************************!#
			!# Welcome to the CCIE Automation script! The purpose              !#
			!# of this script is to streamline your CSR1000v deployment,       !#
			!# as well as the physical switches in your environment. There     !#
			!# are several files you will need to add to the local directory   !#
			!# of this file before proceeding. Please be sure to define the    !#
			!# name EXACTLY as requested.                                      !#
			!#                                                                 !#
			!# 1) userlist.txt - Includes your username and password, both     !#
			!# local as well as RADIUS user password (This script is written   !#
			!# for RADIUS using the FreeRADIUS server only. TACACS+ not        !#
			!# included.                                                       !#  
			!#                                                                 !#
			!# Format (Must match exactly):                                    !#
			!#                                                                 !#
			!# LINE 1: [localuser]                                             !#
			!# LINE 2: [localuser password]                                    !#
			!# LINE 3: [radius user]                                           !#
			!# LINE 4: [radius user password]                                  !#
			!# LINE 5: [SCP Server Username]                                   !#
			!# LINE 6: [SCP Server Password]                                   !#
			!#                                                                 !#
			!# 2) netserver.txt - Includes the IP of the server doing backups. !#
			!#                                                                 !#
			!# Format:                                                         !#
			!#                                                                 !#
			!# LINE 1: [backupserver ip]                                       !#
			!#*****************************************************************!#
		""")
		in_place = query_yes_no("Do you already have the files in place?")
		if in_place == True:
			pass
		else:
			sys.exit("You need the files before you may proceed! Exiting.")
		main_menu = {}
		main_menu['1']="Establish basic connectivity to the boxes"
		main_menu['2']="Perform reachability test"
		main_menu['3']="Convert running configurations to baseline/hardening templates"
		main_menu['4']="Enable premium license (Note: This MUST be enabled for certain scenario configurations!)"
		main_menu['5']="Push Scenario Configurations (INE)"
		main_menu['6']="Run configuration Backup"
		main_menu['7']="Get BGP ASNs for all routers"
		main_menu['8']="Wipe device configurations and start from scratch"
		main_menu['9']="Exit"
		while True:
			options=main_menu.keys()
			options.sort()
			print("!#" + "*" * 95 + "!#")
			print("!#" + " " * 95 + "!#")
			for entry in options:
				print '!# ' + '[+]' + entry, main_menu[entry] + " " * (89 - len(main_menu[entry])) + "!#"
			print("!#" + " " * 95 + "!#")
			print("!#" + "*" * 95 + "!#")
			print("")
			selection=raw_input("[*] Please select the option you'd like to run:\n")
			if selection == '1':
				domainname = raw_input("[?] What is your FQDN?\n")
				create_threads(domainname, localusername, localpassword)
			elif selection == '2':
				ip_reachability_group()
			elif selection == '3':
				choose_scenario_type()
				print("[+] Applying templates...")
				reinitialize_basehardening()
			elif selection == '4':
				device = 'cisco_ios'
				pbar = tqdm(total=100)
				for DeviceName in Device:
					device_ip = Devices[DeviceName][0]
					print("\n[+] Progress:\n")
					install_premium_license(device_ip, device, DeviceName)
				pbar.close()
			elif selection == '5':
				choose_scenario_type()
				print("[+] Verifying device reachability...")
				ip_reachability_group()
				exclude = query_yes_no("[?] Would you like to exclude any additional devices prior to pushing scenario configs?", default="n")
				if exclude == False:
					pass
				else:
					exclude_devices()
				scenario_configuration()
			elif selection == '6':
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
			elif selection == '7':
				print("Getting BGP ASNs for all routers...")
				get_bgp_asn()
			elif selection == '8':
				exclude = query_yes_no("[?] Would you like to exclude any devices from your config wipe?", default="n")
				if exclude == False:
					pass
				else:
					exclude_devices()
				default_configurations()
			elif selection == '9':
				print("Bye")
				break
			else:
				print("[!] Invalid option. Please try again.\n")
	except KeyboardInterrupt:
		print("\n[!] Keyboard Interrupt detected. Goodbye!")
		sys.exit()

call_variables()
main_menu_selection()
