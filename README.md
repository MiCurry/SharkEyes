##Seacast.org
(formerly Project Sharkeyes)

###About
Seacast.org is a Django site created by students at Oregon State University for the College of Earth, Oceanic, and Atmospheric Sciences. It takes oceanic models and uses Matplotlib, Basemap, and Celery to plot them as Google Maps overlays, with the goal of helping Oregon's coastal fisherman find fish more easily.

We have a staging server at [staging.seacast.org](http://staging.seacast.org), and we just deployed to production at seacast.org .

Mobile:

<img src="resources/ios_screenshot.png?raw=true">

Desktop:

<img src="resources/desktop_screenshot.png?raw=true">

###Setup

•	Installation
	•	Prereqs
All these requirements should be cross platform. If you're on Windows, you can also use the Git Bash for these over Command Prompt (lets you use Linux-based commands).
Throughout these steps are mentioned the project directory, which is the directory that you clone from GitHub that contains manage.py and the hidden .git directory.
Anything you see below in italics is a command that can be entered via the commandline.
If you run into an error, there is a list of common problems that we encountered during the setup process near the end of this document in the “Common Problems” section.
	•	Install Vagrant, Git, and VirtualBox (Windows, install 4.3.12 to avoid a bug that wipes your vm.

	•	Install PyCharm (There's a free 30 day trial and free academic license. The community edition doesn't support Django, last I checked, so don't use that one.)


	•	Install Python 2.7 or use the Python that comes with your system. The system python, however, is likely out of date. Don't install Python 3.x, as it is not backwards compatible with 2.x.

	•	Install Python Pip using instructions from here. (Using the get-pip.py script described in the link makes this pretty easy.) Pip is a tool that is used for installing python packages onto your machine.


	•	This step is likely Windows only. You have some dependencies you need to install before installing fabric:
	•	Install the pycrypto binaries with 
	•	easy_install http://www.voidspace.org.uk/downloads/pycrypto26/pycrypto-2.6.win32-py2.7.exe
	•	Then pip install paramiko

	•	Install Fabric with pip install fabric. You can do this in a virtualenv if you want, but it shouldn't conflict with anything so that's likely not critical.

	•	Clone this repo to your local drive using the button (if you use Git Desktop) or the url on the right side of the main github repo page. If you want to use ssh so you don't have to keep entering passwords, learn how to setup ssh keys with GitHub here.
	•	When cloning, keep in mind that you'll be adding a few directories at the same level as the project directory, so the recommended approach is to make a directory for the all this stuff, cd into that, and then clone the repo. (So for example, create directory at ~/code/ and run git clone from inside that directory.)
	•	Clone the repo with 
	•	git clone git@github.com:seacast/SharkEyes.git for ssh,
	•	or git clone https://github.com/seacast/SharkEyes.git for http.

	•	Finally, create a media/ directory at the same level as your project directory. For the example directory structure listed above, it'd be at ~/code/media/, since the repo you just cloned is at~/code/src/ if you specified git clone git@github.com:seacast/SharkEyes.git   /code/src .

Note on SSH keys: you will probably have to set up SSH keys to be able to pull from GitHub: instructions here: https://help.github.com/articles/generating-ssh-keys/
Similarly, if you get an error while doing the clone_repo part of the provisioning on a new server that looks like this: Permission denied (publickey).
fatal: The remote end hung up unexpectedly
I fixed this by creating an SSH key for the server (the Microsoft Azure server in this case; I was able to just provision as normal on the new s-pacifico machine) using the steps in the link above. I followed those steps while I was ssh’ed into the Microsoft server, then added that RSA key using  cat ~/.ssh/id_rsa.pub   to view the key, and added the key to the Seacast github site under “Deploy Keys”. I set a password for this RSA key, so if it asks for a password for RSA keys during deployment on that machine, it is “17Krakens”.

	•	Virtual Machine
	•	Bringing the virtual machine online
	•	While at this point you can just run vagrant up to download and configure the centos box, it's recommended to first download the base box manually.
	•	To download box base manually, you can do vagrant box add centos65 https://github.com/2creatives/vagrant-centos/releases/download/v6.5.3/centos65-x86_64-20140116.box
	•	Then do vagrant up to bring the box online. You'll need to be in or below the directory where the vagrantfile is located. With our running example, you'd need to be in ~/code/src/.
	•	You should now be able to run vagrant ssh from inside the project directory and automatically ssh into the virtual machine. To suspend or shutdown the vm, use vagrant suspend or vagrant halt, respectively. To bring your VM online, it's always vagrant up.
	•	Also check that your local project folder has been mounted in the VM at /vagrant/, by running vagrant ssh and cd’ing into the /vagrant directory.  This makes it easy to edit code in PyCharm or Sublime or something locally, and then run it in the VM without having to copy it.
	•	(Windows users, this would be a good place to check that trying to resume after a vagrant suspend doesn't wipe your VM. There's a bug in some versions of VirtualBox that causes it to lose track of suspended VMs, and then you have to start from scratch. (Look for it unpacking the box again. If it is, then it lost it.) If this is the case, always use vagrant halt.)

	•	Configuring the VM:
Ok, so you've got the vagrant vm up and running. Great! We use fabric to provision the VM and set it up with everything we need. This will take a while to download and compile everything we need, so you can leave it for a bit, but unfortunately it'll need some babysitting at the end.
Setup passwords:
We store the passwords in a separate file that we keep out of source control. Make some up now. You'll need them later in setup, but you can always reference the file you're about to create.
	•	In ~/code/src/SharkEyesCore/ there's a file called settings_local.template. Make a copy of this named settings_local.py and leave it in the same directory.
	•	In this settings_local.py, make up values for the BROKER_PASSWORD and the PASSWORD item under DATABASES. Also, choose a secret key, which should be an ASCII string that's about 40 characters long.
	•	Finally, set the DEBUG and TEMPLATE_DEBUG flags to true if you want the runserver and static files to work.
Setup everything else:
Ok, awesome, vagrant works and you have passwords setup. Now to run the setup script. We use fabric to do this.
	•	Let's test it first. So from the same directory as fabfile.py, or below it, run fab vagrant uname. This will connect to the VM, and run uname -a remotely for you. If this worked, then go to the next step.
	•	Now we install everything on the VM. To do this, run fab vagrant provision. This will take a long time, (possibly hours). It should do most things on its own, but will need babysitting at the end. Just do what it asks you to do. If something fails you should be able to run fab vagrant provision again, as it should be indempotent. If you need to, you can run any function in fabfile.py with fab vagrant <function name>.

Provisioning on a new server: if you get the error
Starting httpd: httpd: Syntax error on line 152 of /etc/httpd/conf/httpd.conf: Cannot load /etc/httpd/modules/mod_wsgi.so into server: libpython2.7.so.1.0: cannot open shared object file: No such file or directory

This may be fixed by doing “fab <target name> restart” so that the disabling of SElinux will take effect. Right now you are asked to restart the system at the very end of the provisioning, but the httpd error listed above seems to indicate we need to restart earlier. Restart() is not built into the script so that you have more control over when the physical machine is rebooted.

If, during the Git portion of the provisioning (which will ask you to hit Enter if you want to run the same branch--yes, do hit Enter), you get an error like this:
error: Your local changes to 'fabfile.py' would be overwritten by merge.  Aborting.
[s-pacifico.coas.oregonstate.edu:22] out: Please, commit your changes or stash them before you can merge.
[s-pacifico.coas.oregonstate.edu:22] out:
Fatal error: run() received nonzero return code 1 while executing!
Requested: git pull
Executed: /bin/bash -l -c "cd /opt/sharkeyes/src/ && git pull"
Fix: ssh into the server you are trying to provision, navigate to the directory where the code is stored, then run “git status” to ensure there is a git repository there. You may need to navigate down into the directory where the code is actually stored, because that is where the git repository is. Then run “git stash” to stash any local changes, so that the git pull which is in the script will not complain. You do not want to make changes directly to the code that is on the server: instead, you should be going through the Deployment process of checking out master, merging your changes in, creating a pull request, then deploying to the server in question. If this is a new machine, Git may ask you to set your name and email address before you can run “git stash”. Once you have done this, exit the ssh session and try the provisioning again.




Database: the MySQL part will prompt you to setup.It will ask for the ROOT password, which is the database root password: ZKbOPUdKWRmJ
Then answer Y (for Yes) for all of the other questions. It asks:
So this script can stop bugging you, first enter your root mysql password:   (this should be ZKbOPUdKWRmJ  on all servers and your local machine)
And now the database password you specified in settings_local.py:(this should be asdf:LKJUIOP on Staging, rrm4wEF8Yu&Y on Production, and whatever you set in YOUR settings_local file on your local machine)
...
What's the Broker password you specified in settings_local.py?: (this should be zBR6sR^QRBgP  on all servers, and whatever passowrd you set in YOUR settings_local file on your local machine)
If it asks if you want to create a Superuser: answer Yes
username should be sharkeyes, password is asdf:LKJUIOP on STAGING or rrm4wEF8Yu&Y on PRODUCTION,  email address is Bethany’s right now (carlsbet) for the main servers. When setting up on your local machine, enter the database password you set in your settings_local file.
If it does NOT ask you if you want to create a super-user, you will need to go back in and do that so that you can login as “sharkeyes”.  You may have to cd into cd /opt/sharkeyes/src/config/  and delete the item named mysql_setup_script_run.guard -- this file says that we have already run the setup, so deleting it allows us to re-setup.



	•	Once that finishes, do fab vagrant deploy to run the Django setup scripts and run the database migrations.
	•	Then do fab vagrant startdev and do what it says to bring all the background services online. You'll need to run this anytime you cold boot the VM. (If you're just resuming, it should be fine.)   (no need to do this if installing on Staging or Production server)
	•	At this point, you can move on and configure PyCharm, or vagrant ssh into the machine and start the runserver manually.
	•	To start the runserver manually, ssh into the vm and source the virtualenv by doing 
source /opt/sharkeyes/env_sharkeyes/bin/activate
	•	Then, from the project directory, do 
./manage.py runserver 0.0.0.0:8000


	•	PyCharm
	•	From PyCharm go File->Open and choose the project directory. It should recognize stuff, give it a chance to do that.
	•	Then you need to setup the project interpreter to use the interpreter in your virtual machine. Make sure the VM is up before doing this:
	•	Go to PyCharm Preferences -> Project Interpretor
	•	Click the gear to the right of the Project Interpeter bar, and then remote, and then the 'vagrant' radio button. If it asks, your vagrant instance folder is the project folder.
	•	In the Python Interpreter Path put /opt/sharkeyes/env_sharkeyes/bin/python

	•	Then click ok. It'll connect to the vagrant instance and learn what's installed there, which might take a minute or two.
	•	Then go to PyCharm Preferences -> Django.
	•	Check the box to enable Django.
	•	The project root is your project folder. Point 'Settings' at settings.py, and point 'Manage script' at manage.py. These are both relative to the project root.

	•	Then setup the site configuration to run the project from within PyCharm:
	•	At the top of the PyCharm window there’s a play button and a down arrow to the left of it. Choose that, and then 'edit configurations'.
	•	Set the host to 0.0.0.0, and the Port to 8000.
	•	Check 'no-reload' so that it doesn’t automatically reload when you change code. Or don't if you want it to do that.
	•	Make sure that the python interpreter is the remote one you made earlier.
	•	Set two environment variables by clicking on the ... to the right of the field.
	•	set DJANGO_SETTINGS_MODULE equal to SharkEyesCore.settings
	•	and set PYTHONUNBUFFERED equal to 1.
	•	And add a path mapping where the local path is your project folder, and the remote path is /opt/sharkeyes/src.
	•	This should be everything. You should be able to hit run, and get then go to localhost:8001 in your browser and see the project home page. If you get a page reset message, try refreshing a few times. If you want to debug, set a breakpoint and hit the bug to the right of the play button.

