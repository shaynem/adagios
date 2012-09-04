# -*- coding: utf-8 -*-
#
# Copyright 2010, Pall Sigurdsson <palli@opensource.is>
#
# This script is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This script is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

from django import forms

from django.core.mail import send_mail
import os.path
from adagios import settings
from pynag import Model, Control

TOPIC_CHOICES = (
    ('general', 'General Suggestion'),
    ('bug', 'I think i have found a bug'),
    ('suggestion', 'I have a particular task in mind that i would like to do with Adagios'),
    ('easier', 'I have an idea how make a certain task easier to do'),
                )

class ContactUsForm(forms.Form):
    topic = forms.ChoiceField(choices=TOPIC_CHOICES)
    sender = forms.CharField(
                            required=False,
                            help_text="Optional email address if you want feedback from us",
                            )
    message = forms.CharField(
                            widget=forms.widgets.Textarea(attrs={'rows':15, 'cols':40}),
                            help_text="See below for examples of good suggestions",
                            )
    def save(self):
        from_address = 'adagios@adagios.opensource.is'
        to_address = ["palli@ok.is"]
        subject = "Suggestion from Adagios"

        sender = self.cleaned_data['sender']
        topic = self.cleaned_data['topic']
        message = self.cleaned_data['message']

        msg = """
        topic: %s
        from: %s

        %s
        """ % (topic,sender,message)
        send_mail(subject, msg, from_address, to_address, fail_silently=False)


class AdagiosSettingsForm(forms.Form):
    nagios_config = forms.CharField(required=False, initial=settings.nagios_config, help_text="Path to nagios configuration file. i.e. /etc/nagios/nagios.cfg")
    nagios_url = forms.CharField(required=False, initial=settings.nagios_url, help_text="URL (relative or absolute) to your nagios webcgi. Adagios will use this to make it simple to navigate from a configured host/service directly to the cgi.")
    nagios_init_script = forms.CharField(help_text="Path to you nagios init script. Adagios will use this when stopping/starting/reloading nagios")
    nagios_binary = forms.CharField(help_text="Path to you nagios daemon binary. Adagios will use this to verify config with 'nagios -v nagios_config'")
    enable_githandler = forms.BooleanField(required=False, initial=settings.enable_githandler, help_text="If set. Adagios will commit any changes it makes to git repository.")
    enable_loghandler = forms.BooleanField(required=False, initial=settings.enable_loghandler, help_text="If set. Adagios will log any changes it makes to a file.")
    warn_if_selinux_is_active = forms.BooleanField(required=False, help_text="Adagios does not play well with SElinux. So lets issue a warning if it is active. Only disable this if you know what you are doing.")
    include = forms.CharField(required=False, help_text="Include configuration options from files matching this pattern")
    def save(self):
        # First of all, if configfile does not exist, lets try to create it:
        if not os.path.isfile( settings.adagios_configfile ):
            open(settings.adagios_configfile, 'w').write()
        for k,v in self.cleaned_data.items():
            Model.config._edit_static_file(attribute=k, new_value=v, filename=settings.adagios_configfile)
            #settings.__dict__[k] = v
    def __init__(self, *args,**kwargs):
        # Since this form is always bound, lets fetch current configfiles and prepare them as post:
        if 'data' not in kwargs or kwargs['data'] == '':
            kwargs['data'] = settings.__dict__
        super(self.__class__,self).__init__(*args,**kwargs)
    def clean_nagios_config(self):
        filename = self.cleaned_data['nagios_config']
        return self.check_file_exists(filename)
    def clean_nagios_init_script(self):
        filename = self.cleaned_data['nagios_init_script']
        if filename.startswith('sudo'):
            filename = filename.split()[1]
        return self.check_file_exists(filename)
    def clean_nagios_binary(self):
        filename = self.cleaned_data['nagios_binary']
        return self.check_file_exists(filename)
    def clean_nagios_config(self):
        filename = self.cleaned_data['nagios_config']
        return self.check_file_exists(filename)
    def check_file_exists(self, filename):
        """ Raises validation error if filename does not exist """
        if not os.path.exists(filename):
            raise forms.ValidationError('File not found')
        return filename

    def clean(self):
        cleaned_data = super(self.__class__, self).clean()
        for k,v in cleaned_data.items():
            # Convert all unicode to quoted strings
            if type(v) == type(u''):
                cleaned_data[k] = str('''"%s"''' % v)
            # Convert all booleans to True/False strings
            elif type(v) == type(False):
                cleaned_data[k] = str(v)
        return cleaned_data

class PNP4NagiosForm(forms.Form):
    """ This form is responsible for configuring PNP4Nagios. """
    broker_module=forms.CharField(help_text="Full path to your npcdmod.o broker module that shipped with your pnp4nagios installation")
    config_file=forms.CharField(help_text="Full path to your npcd.cfg that shipped with your pnp4nagios installation")
    apply_action_url = forms.BooleanField(required=False,initial=True,help_text="If set, apply action_url to every service object in nagios")
    action_url=forms.CharField(required=False,initial="/pnp4nagios/graph?host=$HOSTNAME$&srv=$SERVICEDESC$", help_text="Action url that your nagios objects can use to access perfdata")
    def clean_broker_module(self):
        """ Raises validation error if filename does not exist """
        filename = self.cleaned_data['broker_module']
        if not os.path.exists(filename):
            raise forms.ValidationError('File not found')
        return filename
    def clean_config_file(self):
        """ Raises validation error if filename does not exist """
        filename = self.cleaned_data['config_file']
        if not os.path.exists(filename):
            raise forms.ValidationError('File not found')
        return filename
    def clean_action_url(self):
        return str(self.cleaned_data['action_url'])
    def __init__(self, initial={}, *args,**kwargs):
        my_initial = {}
        Model.config.parse()
        maincfg_values=Model.config.maincfg_values
        self.nagios_configline = None
        for k,v in Model.config.maincfg_values:
            if k == 'broker_module' and v.find('npcdmod.o') > 0:
                self.nagios_configline=v
                v = v.split()
                my_initial['broker_module']=v.pop(0)
                for i in v:
                    if i.find('config_file=') > -1:
                        my_initial['config_file']=i.split('=',1)[1]
        # If view specified any initial values, they overwrite ours
        for k,v in initial.items():
            my_initial[k] = v
        if 'broker_module' not in my_initial:
            my_initial['broker_module'] = self.get_suggested_npcdmod_path()
        if 'config_file' not in my_initial:
            my_initial['config_file'] = self.get_suggested_npcdmod_path()
        super(self.__class__,self).__init__(initial=my_initial,*args,**kwargs)
    def get_suggested_npcdmod_path(self):
        """ Returns best guess for full path to npcdmod.o file """
        possible_locations = [
            "/usr/lib/pnp4nagios/npcdmod.o",
            "/usr/lib64/nagios/brokers/npcdmod.o",
        ]
        for i in possible_locations:
            if os.path.isfile(i):
                return i
        return i
    def get_suggested_npcd_path(self):
        """ Returns best guess for full path to npcd.cfg file """
        possible_locations = [
            "/etc/pnp4nagios/npcd.cfg"
        ]
        for i in possible_locations:
            if os.path.isfile(i):
                return i
        return i
    def save(self):
        if 'broker_module' in self.changed_data or 'config_file' in self.changed_data or self.nagios_configline is None:
            v = "%s config_file=%s" % ( self.cleaned_data['broker_module'], self.cleaned_data['config_file'] )
            Model.config._edit_static_file(attribute="broker_module", new_value=v, old_value = self.nagios_configline, append=True)
        # TODO: What to do if make sure npcd is running is checked
        # TODO: What to do if reload nagios is checked
        if self.cleaned_data['apply_action_url'] == True:
            action_url = self.cleaned_data['action_url']
        services = Model.Service.objects.filter(action_url__isnot=action_url)
        for i in services:
            if 'action_url' in i._defined_attributes or i.use is None:
                i.action_url = action_url
                i.save()


class PerfDataForm(forms.Form):
    perfdata = forms.CharField( widget=forms.Textarea(attrs={ 'wrap':'off', 'cols':'80'}) )
    def save(self):
        from pynag import Model
        perfdata = self.cleaned_data['perfdata']
        perfdata = Model.PerfData(perfdata)
        self.results = perfdata.metrics

COMMAND_CHOICES = [('reload','reload'), ('status','status'),('restart','restart'),('stop','stop'),('start','start')]

class NagiosServiceForm(forms.Form):
    """ Maintains control of the nagios service / reload / restart / etc """
    #path_to_init_script = forms.CharField(help_text="Path to your nagios init script", initial=NAGIOS_INIT)
    #nagios_binary = forms.CharField(help_text="Path to your nagios binary", initial=NAGIOS_BIN)
    #command = forms.ChoiceField(choices=COMMAND_CHOICES)
    def save(self):
        #nagios_bin = self.cleaned_data['nagios_bin']
        if "reload" in self.data:
            command = "reload"
        elif "restart" in self.data:
            command = "restart"
        elif "stop" in self.data:
            command = "stop"
        elif "start" in self.data:
            command = "start"
        elif "status" in self.data:
            command = "status"
        nagios_init = settings.nagios_init_script
        #command = self.cleaned_data['command']
        from subprocess import Popen, PIPE
        command = "%s %s" % (nagios_init, command)
        p = Popen(command.split(), stdout=PIPE, stderr=PIPE)
        self.stdout = p.stdout.read()
        self.stderr = p.stdout.read()
