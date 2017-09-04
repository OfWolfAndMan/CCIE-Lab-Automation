# CCIE-Lab-Automation
## Version 1.17

Use this script to automate a CSR1000V deployment, primarily within a CCIE lab environment.

Built in python 2.7. The following are a few features currently available with this script:

- Basic configuration and in-band IP setup
   
- Baseline and hardening script configuration

- Scenarios configuration per INE's CCIE topology (Will introduce Micronics' labs into the mix soon)

- Configuration backups to an SCP server (A Raspberry Pi was used for testing)

- Install trial premium license for extra functionality i.e. Security and Data licenses (MPLS, IPSec)

**Prerequisites & Dependencies:**

	* Python (Duh)

	* Required libraries

	   + Netmiko
	  
	   + All other libraries come with python 2.7 natively
	   
	   + TQDM (Used as a progress bar for tasks)

	* SCP server for backups (Can modify for FTP)

	* RADIUS or TACACS+ server for authentication (FreeRADIUS was used in testing on a Raspberry Pi)

**New in this release:**

	[+] TQDM progress bar features
	
	[+] Eliminate need to reload after completion of configuration by introducing the "configure replace" option
	
	[+] Improved decision logic
	
	[+] Usernames/passwords for local, TACACS+/RADIUS, and SCP logins have been moved to a separate file to allow more flexibility.

**(Potential) Future Development:**

	[+] TextFSM integration for data parsing

	[+] Ansible integration for supplementary configuration management purposes

	[+] Jinja2 integration for ease of configuration templating
	
**Caveats:**

Baseline script formatting must have the following requirements for configure replace to take it properly:
	
	- "Version 15.4" (Or the applicable version)
	
	- "end" command
	
	- Subcommands, such as those under "interface Gigx/x", must have a space in them to display hierarchy. Otherwise those lines
	won't be added.

Paths should be defined in the script to suit your needs. Things that may need to be changed in the script includes:
	
	-SCP server IP
	
	-SCP server path
	
	-Router/Switch serial IPs and ports, and in-band IPs
	
	-Path to your scenario/baseline/hardening configurations on the box running the script

**Known Bugs:**

When using the "configure replace" command on the CSRs, it has been discovered that the CSR may reload without user intervention. It is uncertain if this is specific to the version of CSR code, or the hardware it is virtualized in.