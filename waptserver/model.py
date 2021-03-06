#!/usr/bin/python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
#    This file is part of WAPT
#    Copyright (C) 2013  Tranquil IT Systems http://www.tranquil.it
#    WAPT aims to help Windows systems administrators to deploy
#    setup and update applications on users PC.
#
#    WAPT is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    WAPT is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with WAPT.  If not, see <http://www.gnu.org/licenses/>.
#
# -----------------------------------------------------------------------

import os
import sys
import uuid as _uuid

import psutil
import datetime
import subprocess
import getpass
import traceback
import platform

from peewee import *
from peewee import Function
from waptserver.config import __version__

from playhouse.postgres_ext import *
from playhouse.pool import PooledPostgresqlExtDatabase

from playhouse.shortcuts import dict_to_model, model_to_dict
from playhouse.signals import Model as SignaledModel, pre_save, post_save

from waptutils import Version
from waptutils import ensure_unicode,ensure_list

from waptserver.utils import setloglevel

import json
import codecs
import datetime
import os

from optparse import OptionParser

import waptserver.config

# You must be sure your database is an instance of PostgresqlExtDatabase in order to use the JSONField.

import logging
logger = logging.getLogger()

wapt_db = Proxy()

def load_db_config(server_config=None):
    """Initialise db proxy with parameters from inifile

    Args:
        serverconfig (dict): dict of server parameters as returned by waptserver.config.load_config(ainifilename)

    Returns
        configured db : db which has been put in wapt_db proxy
    """
    global wapt_db
    if server_config is None:
        server_config = waptserver.config.load_config()

    logger.info('Initializing a DB connection pool for db host:%s db_name:%s. Size:%s' %
        (server_config['db_host'],server_config['db_name'],server_config['db_max_connections']))
    pgdb = PooledPostgresqlExtDatabase(
        database=server_config['db_name'],
        host=server_config['db_host'],
        user=server_config['db_user'],
        password=server_config['db_password'],
        max_connections=server_config['db_max_connections'],
        stale_timeout=server_config['db_stale_timeout'],
        timeout=server_config['db_connect_timeout'])
    wapt_db.initialize(pgdb)
    return pgdb

class WaptBaseModel(SignaledModel):
    """A base model that will use our Postgresql database"""
    class Meta:
        database = wapt_db

    # audit data
    created_on = DateTimeField(null=True)
    created_by = DateTimeField(null=True)
    updated_on = DateTimeField(null=True)
    updated_by = DateTimeField(null=True)

    def __unicode__(self):
        return u'%s' % (self.__data__,)

    def __str__(self):
        return self.__unicode__().encode('utf8')


@pre_save(sender=WaptBaseModel)
def waptbasemodel_pre_save(model_class, instance, created):
    if created:
        instance.created_on = datetime.datetime.now()
    instance.updated_on = datetime.datetime.now()


class ServerAttribs(SignaledModel):
    """key/value registry"""
    class Meta:
        database = wapt_db

    key = CharField(primary_key=True, null=False, index=True)
    value = BinaryJSONField(null=True)

    @classmethod
    def dump(cls):
        for key, value in cls.select(cls.key, cls.value).tuples():
            print(u'%s: %s' % (key, repr(value)))

    @classmethod
    def get_value(cls, key):
        v = cls.select(cls.value).where(cls.key == key).dicts().first()
        if v:
            return v['value']
        else:
            return None

    @classmethod
    def set_value(cls, key, value):
        with cls._meta.database.atomic():
            try:
                cls.create(key=key, value=value)
            except IntegrityError:
                wapt_db.rollback()
                cls.update(value=value).where(cls.key == key).execute()

    def __unicode__(self):
        return u'%s' % (self.__data__,)

    def __str__(self):
        return self.__unicode__().encode('utf8')

class Hosts(WaptBaseModel):
    """Inventory informations of a host
    """
    # from bios
    uuid = CharField(primary_key=True, index=True)

    # inventory type data (updated on register)
    computer_fqdn = CharField(null=True, index=True)
    description = CharField(null=True, index=True)
    computer_name = CharField(null=True)
    computer_type = CharField(null=True)  # tower, laptop,etc..
    computer_architecture = CharField(null=True)  # tower, laptop,etc..
    manufacturer = CharField(null=True)
    productname = CharField(null=True)
    serialnr = CharField(null=True)

    host_certificate = TextField(null=True, help_text='Host public X509 certificate bundle')
    registration_auth_user = CharField(null=True)

    #authorized_certificates = ArrayField(CharField, null=True, help_text='authorized packages signers certificates sha1 fingerprint')

    os_name = CharField(null=True)
    os_version = CharField(null=True)
    os_architecture = CharField(null=True)

    # frequently updated data from host update_status
    connected_users = ArrayField(CharField, null=True)
    connected_ips = ArrayField(CharField, null=True)
    mac_addresses = ArrayField(CharField, null=True)
    gateways = ArrayField(CharField, null=True)
    networks = ArrayField(CharField, null=True)
    dnsdomain = CharField(null=True)

    computer_ad_site = CharField(null=True,index=True)
    computer_ad_ou = CharField(null=True,index=True)
    computer_ad_groups = ArrayField(CharField, null=True)

    # calculated by server when update_status
    reachable = CharField(20, null=True)

    # for websockets
    server_uuid = CharField(null=True)
    listening_protocol = CharField(10, null=True)
    # in case of websockets, this stores the sid
    listening_address = CharField(null=True)
    listening_port = IntegerField(null=True)
    listening_timestamp = CharField(null=True)

    host_status = CharField(null=True)
    last_seen_on = CharField(null=True)
    last_logged_on_user = CharField(null=True)

    audit_status = CharField(null=True)

    # raw json data
    wapt_status = BinaryJSONField(null=True)
    # running, pending, errors, finished , upgradable, errors,
    last_update_status = BinaryJSONField(null=True)
    host_info = BinaryJSONField(null=True)

    # variable structures... so keep them as json
    dmi = BinaryJSONField(null=True)
    wmi = BinaryJSONField(null=True)

    """
    def save(self,*args,**argvs):
        if 'uuid' in self._dirty:
            argvs['force_insert'] = True
        return super(Hosts,self).save(*args,**argvs)
    """

    def __repr__(self):
        return '<Host fqdn=%s / uuid=%s>' % (self.computer_fqdn, self.uuid)

    @classmethod
    def fieldbyname(cls, fieldname):
        return cls._meta.fields[fieldname]

class HostPackagesStatus(WaptBaseModel):
    """Stores the status of packages installed on a host
    """
    id = PrimaryKeyField(primary_key=True)
    host = ForeignKeyField(Hosts, on_delete='CASCADE', on_update='CASCADE')
    package = CharField(null=True, index=True)
    version = CharField(null=True)
    architecture = CharField(null=True)
    locale = CharField(null=True)
    maturity = CharField(null=True)
    section = CharField(null=True)
    priority = CharField(null=True)
    signer = CharField(null=True)
    signer_fingerprint = CharField(null=True)
    description = TextField(null=True)
    install_status = CharField(null=True)
    install_date = CharField(null=True)
    install_output = TextField(null=True)
    install_params = CharField(null=True)
    uninstall_key = CharField(null=True)
    explicit_by = CharField(null=True)
    repo_url = CharField(max_length=600, null=True)
    depends = ArrayField(CharField,null=True)
    conflicts = ArrayField(CharField,null=True)
    last_audit_status = CharField(null=True)
    last_audit_on = CharField(null=True)
    last_audit_output = TextField(null=True)
    next_audit_on = CharField(null=True)

    def __repr__(self):
        return '<HostPackageStatus uuid=%s packages=%s (%s) install_status=%s>' % (self.id, self.package, self.version, self.install_status)

class Packages(WaptBaseModel):
    """Stores the content of packages of repositories
    """
    id = PrimaryKeyField(primary_key=True)
    package = CharField(null=False, index=True)
    version = CharField(null=False)
    description = CharField(max_length=1200,null=True)
    architecture = CharField(null=True)
    locale = CharField(null=True)
    maturity = CharField(null=True)
    section = CharField(null=True)
    priority = CharField(null=True)
    signer = CharField(null=True)
    signer_fingerprint = CharField(null=True)
    description = TextField(null=True)
    depends = ArrayField(CharField,null=True)
    conflicts = ArrayField(CharField,null=True)

    @classmethod
    def _as_attribute(cls,k,v):
        if k in ['depends','conflicts']:
            return ensure_list(v or None)
        else:
            return v or None

    @classmethod
    def from_control(cls,entry):
        package = cls(** dict((a,cls._as_attribute(a,v)) for (a,v) in entry.as_dict().iteritems() if a in cls._meta.columns))

    @classmethod
    def update_from_repo(cls,repo):
        """
        Args:
            repo (WaptRepo):
        Returns:
            list of PackagEntry added to the table
        """
        result = []
        for pe in repo.packages:
            key = {'package':pe.package,'version':pe.version,'architecture':pe.architecture,'locale':pe.locale,'maturity':pe.maturity}
            (rec,_isnew) = Packages.get_or_create(**key)
            for (a,v) in pe.as_dict().iteritems():
                if a in cls._meta.columns and not a in key:
                    new_value = cls._as_attribute(a,v)
                    if new_value != getattr(rec,a):
                        setattr(rec,a,cls._as_attribute(a,v))
            if rec.is_dirty():
                rec.save()
            if _isnew:
                result.append(pe)
        return result


class HostSoftwares(WaptBaseModel):
    id = PrimaryKeyField(primary_key=True)
    host = ForeignKeyField(Hosts, on_delete='CASCADE', on_update='CASCADE')
    name = CharField(max_length=2000, null=True, index=True)
    version = CharField(max_length=1000, null=True)
    publisher = CharField(max_length=2000, null=True)
    key = CharField(max_length=600, null=True)
    system_component = CharField(null=True)
    uninstall_string = CharField(max_length=2000, null=True)
    install_date = CharField(null=True)
    install_location = CharField(max_length=2000, null=True)

    def __repr__(self):
        return '<HostSoftwares uuid=%s name=%s (%s) key=%s>' % (self.uuid, self.name, self.version, self.key)


class HostGroups(WaptBaseModel):
    id = PrimaryKeyField(primary_key=True)
    host = ForeignKeyField(Hosts, on_delete='CASCADE', on_update='CASCADE')
    group_name = CharField(null=False, index=True)

    def __repr__(self):
        return '<HostGroups uuid=%s group_name=%s>' % (self.uuid, self.group_name)


class HostJsonRaw(WaptBaseModel):
    id = PrimaryKeyField(primary_key=True)
    host = ForeignKeyField(Hosts, on_delete='CASCADE', on_update='CASCADE')


class HostWsus(WaptBaseModel):
    id = PrimaryKeyField(primary_key=True)
    host = ForeignKeyField(Hosts, on_delete='CASCADE', on_update='CASCADE')
    # windows updates
    wsus = BinaryJSONField(null=True)

class SignedModel(WaptBaseModel):
    uuid = CharField(primary_key=True,null=False,default=str(_uuid.uuid4()))

    def save(self,*args,**argvs):
        if 'uuid' in self._dirty:
            argvs['force_insert'] = True
        return super(SignedModel,self).save(*args,**argvs)


class WsusUpdates(WaptBaseModel):
    id = PrimaryKeyField(primary_key=True)
    update_id = CharField()
    revision_id = CharField()
    revision_number = IntegerField()
    title = CharField(null=True)
    description = CharField(null=True)
    msrc_severity = CharField(null=True)
    security_bulletin_id = CharField(null=True)
    kb_article_id = CharField(null=True)
    creation_date = CharField(null=True)
    is_bundle = BooleanField()
    is_leaf = BooleanField()
    deployment_action = CharField(null=True)
    company = CharField(null=True)
    product = CharField(null=True)
    product_family = CharField(null=True)
    update_classification = CharField(null=True)
    languages = ArrayField(CharField, null=True)
    prereqs_update_ids = ArrayField(CharField, null=True)
    payload_files = ArrayField(CharField, null=True)


class WsusLocations(WaptBaseModel):
    id = IntegerField(primary_key=True)
    url = CharField(null=True)

class WsusScan2History(WaptBaseModel):
    id = PrimaryKeyField(primary_key=True)
    run_date = DateTimeField(null=True,index=True)
    status = CharField(null=True)
    reason = CharField(null=True)
    forced = BooleanField(null=True)
    skipped = BooleanField(null=True)
    file_date = DateTimeField(null=True)
    file_size = IntegerField(null=True)
    target_size = IntegerField(null=True)
    cablist = ArrayField(CharField, null=True)
    error = CharField(max_length=1200,null=True)

class WsusCabsInfos(WaptBaseModel):
    id = PrimaryKeyField(primary_key=True)
    cab_name = CharField(unique=True,index=True)
    sha1_ckecksum = CharField(null=True)


def dictgetpath(adict, pathstr):
    """Iterates a list of path pathstr of the form 'key.subkey.sskey' and returns
    the first occurence in adict which returns not None.

    A path component can contain a wildcard '*' to match an array.

    """
    if not isinstance(pathstr, (list, tuple)):
        pathstr = [pathstr]
    for path in pathstr:
        result = adict
        for k in path.split('.'):
            if isinstance(result, dict):
                # assume this level is an object and returns the specified key
                result = result.get(k)
            elif isinstance(result, list) and k.isdigit() and int(k) < len(result):
                # assume this level is a list and return the n'th item
                result = result[k]
            elif k == '*' and isinstance(result, list):
                # assume this level is an array, and iterates all items
                continue
            elif isinstance(k, (str, unicode)) and isinstance(result, list):
                # iterate through a list returning only a key
                result = [item.get(k) for item in result if item.get(k)]
            else:
                # key not found, we have to retry with next path
                result = None
                break
        if result:
            break
    return result


def set_host_field(host, fieldname, data):
    # these attributes can be transfered as dict
    if fieldname in ['installed_softwares', 'installed_packages']:
        # in case data is transfered as list of tuples instead of list of dict (more compact)
        if data and isinstance(data[0], list):
            rec_data = []
            fieldnames = data[0]
            for rec in data[1:]:
                r = zip(fieldnames, rec)
                rec_data.append(r)
            setattr(host, fieldname, rec_data)
        else:
            setattr(host, fieldname, data)
    else:
        # awfull hack for data containing null char, not accepted by postgresql.
        if fieldname in ('host_info', 'wmi', 'dmi'):
            jsonrepr = json.dumps(data)
            if '\u0000' in jsonrepr:
                logger.warning('Workaround \\u0000 not handled by postgresql json for host %s field %s' % (getattr(host, 'uuid', '???'), fieldname))
                data = json.loads(jsonrepr.replace('\u0000', ' '))

        setattr(host, fieldname, data)
    return host


def update_installed_packages(uuid, installed_packages):
    """Stores packages json data into separate HostPackagesStatus

    Args:
        uuid (str) : unique ID of host
        installed_packages (list): data from host
    Returns:

    """
    # TODO : be smarter : insert / update / delete instead of delete all / insert all ?
    # is it faster ?
    key = ['package','version','version','architecture','locale','maturity']
    def get_key(rec):
        return {k:rec[k] for k in rec}
    #old_installed = HostPackagesStatus.select().where(HostPackagesStatus.host == uuid).dicts()

    def encode_value(value):
        if isinstance(value,unicode):
            value = value.replace(u'\x00', ' ')
        return value

    HostPackagesStatus.delete().where(HostPackagesStatus.host == uuid).execute()
    packages = []
    for package in installed_packages:
        package['host'] = uuid
        # csv str on the client, Array on the server
        package['depends'] = ensure_list(package['depends'])
        package['conflicts'] = ensure_list(package['conflicts'])

        # filter out all unknown fields from json data for the SQL insert
        packages.append(dict([(k, encode_value(v)) for k, v in package.iteritems() if k in HostPackagesStatus._meta.fields]))
    if packages:
        return HostPackagesStatus.insert_many(packages).execute() # pylint: disable=no-value-for-parameter
    else:
        return True


def update_installed_softwares(uuid, installed_softwares):
    """Stores softwares json data into separate HostSoftwares table

    Args:
        uuid (str) : unique ID of host
        installed_packages (list): data from host
    Returns:

    """
    # TODO : be smarter : insert / update / delete instead of delete all / insert all ?
    HostSoftwares.delete().where(HostSoftwares.host == uuid).execute()
    softwares = []

    def encode_value(value):
        if isinstance(value,unicode):
            value = value.replace(u'\x00', ' ')
        return value

    for software in installed_softwares:
        software['host'] = uuid
        # filter out all unknown fields from json data for the SQL insert
        softwares.append(dict([(k,encode_value(v)) for k, v in software.iteritems() if k in HostSoftwares._meta.fields]))
    if softwares:
        return HostSoftwares.insert_many(softwares).execute() # pylint: disable=no-value-for-parameter
    else:
        return True


def update_host_data(data):
    """Helper function to insert or update host data in db

    Args :
        data (dict) : data to push in DB with at least 'uuid' key
                        if uuid key already exists, update the data
                        eld insert
                      only keys in data are pushed to DB.
                        Other data (fields) are left untouched
    Returns:
        dict : with uuid,computer_fqdn,host_info from db after update
    """
    migrate_map_13_14 = {
        'packages': None,
        'installed_packages': None,
        'softwares': None,
        'installed_softwares': None,

        'update_status': 'last_update_status',
        'host': 'host_info',
        'wapt': 'wapt_status',
        'update_status': 'last_update_status',
    }

    uuid = data['uuid']
    try:
        existing = Hosts.select(Hosts.uuid, Hosts.computer_fqdn).where(Hosts.uuid == uuid).first()
        if not existing:
            logger.debug('Inserting new host %s with fields %s' % (uuid, data.keys()))
            # wapt update_status packages softwares host
            newhost = Hosts()
            for k in data.keys():
                # manage field renaming between 1.3 and >= 1.4
                target_key = migrate_map_13_14.get(k, k)
                if target_key and hasattr(newhost, target_key):
                    set_host_field(newhost, target_key, data[k])

            newhost.save(force_insert=True)
        else:
            logger.debug('Updating %s for fields %s' % (uuid, data.keys()))

            updhost = Hosts.get(uuid=uuid)
            for k in data.keys():
                # manage field renaming between 1.3 and >= 1.4
                target_key = migrate_map_13_14.get(k, k)
                if target_key and hasattr(updhost, target_key):
                    set_host_field(updhost, target_key, data[k])
            updhost.save()

        # separate tables
        # we are tolerant on errors here a we don't know exactly if client send good encoded data
        # but we still want to get host in table
        try:
            if ('installed_softwares' in data) or ('softwares' in data):
                installed_softwares = data.get('installed_softwares', data.get('softwares', None))
                if not update_installed_softwares(uuid, installed_softwares):
                    logger.critical('Unable to update installed_softwares for %s' % uuid)
        except Exception as e:
            logger.critical(u'Unable to update installed_softwares for %s: %s' % (uuid,traceback.format_exc()))

        try:
            if ('installed_packages' in data) or ('packages' in data):
                installed_packages = data.get('installed_packages', data.get('packages', None))
                if not update_installed_packages(uuid, installed_packages):
                    logger.critical('Unable to update installed_packages for %s' % uuid)
        except Exception as e:
            logger.critical(u'Unable to update installed_packages for %s: %s' % (uuid,traceback.format_exc()))

        try:
            if ('waptwua' in data):
                waptwua_data = data.get('waptwua', None)
                (rec,_) = HostWsus.get_or_create(host=uuid)
                rec.wsus = waptwua_data
                rec.save()
        except Exception as e:
            logger.critical(u'Unable to update wsus data for %s: %s' % (uuid,traceback.format_exc()))

        result_query = Hosts.select(Hosts.uuid, Hosts.computer_fqdn)
        return result_query.where(Hosts.uuid == uuid).dicts().first()

    except Exception as e:
        logger.warning(traceback.format_exc())
        logger.critical(u'Error updating data for %s : %s' % (uuid, ensure_unicode(e)))
        wapt_db.rollback()
        raise e



@pre_save(sender=Hosts)
def wapthosts_json(model_class, instance, created):
    """Stores in plain table fields data from json"""
    # extract data from json into plain table fields
    if (created or Hosts.host_info in instance.dirty_fields) and instance.host_info:
        def extract_ou(host_info):
            dn =  host_info.get('computer_ad_dn',None)
            if dn:
                parts = dn.split(',',1)
                if len(parts)>=2:
                    return parts[1]
                else:
                    return ''
            else:
                return None

        extractmap = [
            ['computer_fqdn', 'computer_fqdn'],
            ['computer_name', 'computer_name'],
            ['description', 'description'],
            ['manufacturer', 'system_manufacturer'],
            ['productname', 'system_productname'],
            ['os_name', 'windows_product_infos.version'],
            ['os_version', ('windows_version', 'windows_product_infos.windows_version')],
            ['connected_ips', 'connected_ips'],
            ['connected_users', ('connected_users', 'current_user')],
            ['last_logged_on_user', 'last_logged_on_user'],
            ['mac_addresses', 'mac'],
            ['dnsdomain', ('dnsdomain', 'dns_domain')],
            ['gateways', 'gateways'],
            ['computer_ad_site', 'computer_ad_site'],
            ['computer_ad_ou', extract_ou],
            ['computer_ad_groups', 'computer_ad_groups'],
        ]

        for field, attribute in extractmap:
            if callable(attribute):
                setattr(instance, field, attribute(instance.host_info))
            else:
                setattr(instance, field, dictgetpath(instance.host_info, attribute))

        instance.os_architecture = 'x64' and instance.host_info.get('win64', '?') or 'x86'

    if (created or Hosts.dmi in instance.dirty_fields) and instance.dmi:
        extractmap = [
            ['serialnr', 'Chassis_Information.Serial_Number'],
            ['computer_type', 'Chassis_Information.Type'],
        ]
        for field, attribute in extractmap:
            if callable(attribute):
                setattr(instance, field, attribute(instance.dmi))
            else:
                setattr(instance, field, dictgetpath(instance.dmi, attribute))

    if not instance.connected_ips:
        instance.connected_ips = dictgetpath(instance.host_info, 'networking.*.addr')

    # update host update status based on update_status json data or packages collection
    if not instance.host_status or created or Hosts.last_update_status in instance.dirty_fields:
        instance.host_status = None
        if instance.last_update_status:
            if instance.last_update_status.get('errors', []):
                instance.host_status = 'ERROR'
            elif instance.last_update_status.get('upgrades', []):
                instance.host_status = 'TO-UPGRADE'
        if not instance.host_status:
            instance.host_status = 'OK'


class ColumnDef(object):
    """Holds definitin of column for updatable remote GUI table
    """

    def __init__(self,field,in_update=None,in_where=None,in_key=None):
        self.field = field
        if in_update is not None:
            self.in_update = in_update
        else:
            self.in_update = not isinstance(field,ForeignKeyField) and not isinstance(field,Function)

        self.in_where = None
        if in_where is not None:
            self.in_where = in_where

        if in_where is None:
            self.in_where = not isinstance(field,ForeignKeyField) and not isinstance(field,Function)

        self.in_key = field.primary_key
        self.visible = False
        self.default_width = None

    def as_metadata(self):
        result = dict()
        if isinstance(self.field,Function):
            result = {'name':self.field._alias or self.field.name,'org_name':self.field.name,'type':self.field._node_type}
        else:
            result = {'name':self.field._alias or self.field.name,
                'field_name':self.field.name,
                'type':self.field.field_type,
                'table_name':self.field.model._meta.table_name,
                }

            attlist = ('primary_key','description','help_text','choice',
                        'default','sequence','max_length')
            for att in attlist:
                if hasattr(self.field,att):
                    value = getattr(self.field,att)
                    if value is not None and not isinstance(value,Function):
                        if callable(value):
                            result[att] = value()
                        else:
                            result[att] = value


        for att in ('visible','default_width'):
            value = getattr(self,att)
            if value is not None:
                if callable(value):
                    result[att] = value()
                else:
                    result[att] = value

        result['required'] = not self.field.is_null()
        return result

    def to_client(self,data):
        """Return a serialization of data, suitable for client application"""
        if isinstance(data,list):
            return json.dumps(data)
        else:
            return data

    def from_client(self,data):
        """Return db suitable value from a serialization from client application"""
        if isinstance(self.field,ArrayField):
            return json.loads(data)
        else:
            return data

class TableProvider(object):
    """Updatable dataset provider based on a list of column defs and
    a where clause.

    >>>
    """
    def __init__(self,query=None,model=None,columns=None,where=None):
        self.query = query
        self.model = model
        self.columns = columns
        self.where = where

        if not self.model and self.query:
            (fields,joins) = self.query.get_query_meta()
            if len(joins) != 1:
                raise Exception('Unable to guess model from query, please provide a model argument')
            self.model = joins.keys()[0]

        if not self.query and not self.model:
            raise Exception('Either query or model must be supplied')
        self._columns_idx = None


    def _init_columns_from_query(self,query):
        if self.columns is None:
            self.columns = []
        (fields,joins) = query.get_query_meta()
        for field in fields:
            column = ColumnDef(field)
            self.columns.append(column)

    def get_data(self,start=0,count=None):
        """Build query, retrieve rows"""

        fields_list = []
        query = self.query
        if not query and self.model:
            query = self.model.select(* [f.field for f in self.columns])
            if self.where:
                query = query.where(self.where)

        if not self.columns:
            self._init_columns_from_query(query)

        columns_names = [column.field.column_name for column in self.columns]
        rows = []
        for row in query.dicts():
            rows.append([column.to_client(row[column.field._alias or column.field.column_name]) for column in self.columns])

        return dict(
            metadata = [c.as_metadata() for c in self.columns],
            rows = rows
        )

    def column_by_name(self,name):
        """Return ColumnDef for field name"""
        if self._columns_idx is None:
            self._columns_idx = dict([(c.field.column_name,c) for c in self.columns])
        return self._columns_idx.get(name,None)

    def _where_from_values(self,old_values={}):
        """Return a where clause from old and new dict for update and delete"""
        result = None
        for (column_name,column_value) in old_values.iteritems():
            column = self.column_by_name(column_name)
            if column:
                if column.in_key or column.in_where:
                    if result is None:
                        result = column.field == column_value
                    else:
                        result = result & column.field == column_value
        return result

    def _record_values_from_values(self,new_values={}):
        """Return a dict for the insert/update into database from supplkied dict
        filtering out non updateable values.
        """
        result = {}
        for (column_name,column_value) in new_values.iteritems():
            column = self.column_by_name(column_name)
            if column:
                if column.in_update:
                    result[column_name] = column.from_client(column_value)
        return result

    def _values_from_record_values(self,values):
        """Return a dict
        """
        result = {}
        for (column_name,column_value) in values.iteritems():
            column = self.column_by_name(column_name)
            if column:
                result[column_name] = column.to_client(column_value)
        return result

    def _update_set_from_values(self,new_values={}):
        """Return a dict for the insert/update into database from supplkied dict
        filtering out non updateable values.
        """
        result = {}
        for (column_name,column_value) in new_values.iteritems():
            column = self.column_by_name(column_name)
            if column:
                if column.in_update:
                    result[column.field] = column.from_client(column_value)
        return result

    def apply_updates(self,delta):
        """Build update queries from delta

        Args:
            delta (list): list of (update_type,old_data,new_data)
                update_type (str) = ('insert','update','delete')
                old_data (dict)  = empty dict for insert, list of old values for update / delete.
                           must include in_key, in_where, and updated fields with in_update flag
                new_data (dict) = dict for updated / inserted data, empty for delete

        """
        result = []
        with self.model._meta.database.atomic():
            for (update_type,old,new) in delta:
                # translates old / new value to
                if update_type == 'insert':
                    query = self.model.insert(self._update_set_from_values(new))
                elif update_type == 'update':
                    old_db_values = self._record_values_from_values(old)
                    query = self.model.update(self._update_set_from_values(new)).where(self._where_from_values(old_db_values))
                elif update_type == 'delete':
                    old_db_values = self._record_values_from_values(old)
                    query = self.model.delete().where(self._where_from_values(old_db_values))
                query.execute()
        return result


def get_db_version():
    try:
        return Version(ServerAttribs.get(key='db_version').value, 4)
    except:
        wapt_db.rollback()
        return None


def init_db(drop=False):
    wapt_db.connection()
    try:
        wapt_db.execute_sql('CREATE EXTENSION hstore;')
    except:
        wapt_db.rollback()
    if drop:
        for table in reversed([ServerAttribs, Hosts, HostPackagesStatus, HostSoftwares, HostJsonRaw, HostWsus,HostGroups,WsusScan2History]):
            table.drop_table(fail_silently=True)
    wapt_db.create_tables([ServerAttribs, Hosts, HostPackagesStatus, HostSoftwares, HostJsonRaw, HostWsus,HostGroups,WsusScan2History], safe=True)

    if get_db_version() == None:
        # new database install, we setup the db_version key
        (v, created) = ServerAttribs.get_or_create(key='db_version')
        v.value = __version__
        v.save()

    if get_db_version() != __version__:
        with wapt_db.atomic():
            upgrade_db_structure()
            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = __version__
            v.save()
    return get_db_version()


def upgrade_db_structure():
    """Upgrade the tables version by version"""
    from playhouse.migrate import PostgresqlMigrator, migrate
    migrator = PostgresqlMigrator(wapt_db)
    logger.info('Current DB: %s version: %s' % (wapt_db.connect_params, get_db_version()))

    # from 1.4.1 to 1.4.2
    if get_db_version() < '1.4.2':
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), '1.4.2'))
            migrate(
                migrator.rename_column(Hosts._meta.name, 'host', 'host_info'),
                migrator.rename_column(Hosts._meta.name, 'wapt', 'wapt_status'),
                migrator.rename_column(Hosts._meta.name, 'update_status', 'last_update_status'),

                migrator.rename_column(Hosts._meta.name, 'softwares', 'installed_softwares'),
                migrator.rename_column(Hosts._meta.name, 'packages', 'installed_packages'),
            )
            HostGroups.create_table(fail_silently=True)
            HostJsonRaw.create_table(fail_silently=True)
            HostWsus.create_table(fail_silently=True)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = '1.4.2'
            v.save()

    next_version = '1.4.3'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            if not [c.name for c in wapt_db.get_columns('hosts') if c.name == 'host_certificate']:
                migrate(
                    migrator.add_column(Hosts._meta.name, 'host_certificate', Hosts.host_certificate),
                )

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.4.3.1'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            columns = [c.name for c in wapt_db.get_columns('hosts')]
            opes = []
            if not 'last_logged_on_user' in columns:
                opes.append(migrator.add_column(Hosts._meta.name, 'last_logged_on_user', Hosts.last_logged_on_user))
            if 'installed_sofwares' in columns:
                opes.append(migrator.drop_column(Hosts._meta.name, 'installed_sofwares'))
            if 'installed_sofwares' in columns:
                opes.append(migrator.drop_column(Hosts._meta.name, 'installed_packages'))
            migrate(*opes)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.4.3.2'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            wapt_db.execute_sql('''\
                ALTER TABLE hostsoftwares
                    ALTER COLUMN publisher TYPE character varying(2000),
                    ALTER COLUMN version TYPE character varying(1000);''')
            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.5.0.4'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            columns = [c.name for c in wapt_db.get_columns('hosts')]
            opes = []
            if not 'server_uuid' in columns:
                opes.append(migrator.add_column(Hosts._meta.name, 'server_uuid', Hosts.server_uuid))
            migrate(*opes)
            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.5.0.11'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            HostGroups.create_table(fail_silently=True)
            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.5.1.1'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            columns = [c.name for c in wapt_db.get_columns('hosts')]
            opes = []
            if not 'computer_ad_site' in columns:
                opes.append(migrator.add_column(Hosts._meta.name, 'computer_ad_site', Hosts.computer_ad_site))
            if not 'computer_ad_ou' in columns:
                opes.append(migrator.add_column(Hosts._meta.name, 'computer_ad_ou', Hosts.computer_ad_ou))
            if not 'computer_ad_groups' in columns:
                opes.append(migrator.add_column(Hosts._meta.name, 'computer_ad_groups', Hosts.computer_ad_groups))
            migrate(*opes)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.5.1.3'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            columns = [c.name for c in wapt_db.get_columns('hosts')]
            opes = []
            if not 'registration_auth_user' in columns:
                opes.append(migrator.add_column(Hosts._meta.name, 'registration_auth_user', Hosts.registration_auth_user))
            migrate(*opes)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.5.1.14'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            columns = [c.name for c in wapt_db.get_columns('hostpackagesstatus')]
            opes = []
            if not 'depends' in columns:
                opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'depends', HostPackagesStatus.depends))
            if not 'conflicts' in columns:
                opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'conflicts', HostPackagesStatus.conflicts))
            migrate(*opes)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.5.1.17'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            opes = []
            ##
            migrate(*opes)

            WsusScan2History.create_table(fail_silently=True)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.5.1.22'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            opes = []
            opes.append(migrator.drop_column(HostPackagesStatus._meta.name, 'depends'))
            opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'depends', HostPackagesStatus.depends))
            opes.append(migrator.drop_column(HostPackagesStatus._meta.name, 'conflicts'))
            opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'conflicts', HostPackagesStatus.conflicts))
            migrate(*opes)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.6.0.0'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            opes = []
            opes.append(migrator.add_column(Hosts._meta.name, 'audit_status', Hosts.audit_status))

            opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'last_audit_status', HostPackagesStatus.last_audit_status))
            opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'last_audit_on', HostPackagesStatus.last_audit_on))
            opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'last_audit_output', HostPackagesStatus.last_audit_output))
            opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'next_audit_on', HostPackagesStatus.next_audit_on))
            migrate(*opes)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()

    next_version = '1.6.0.1'
    if get_db_version() < next_version:
        with wapt_db.atomic():
            logger.info('Migrating from %s to %s' % (get_db_version(), next_version))
            opes = []
            opes.append(migrator.add_column(HostPackagesStatus._meta.name, 'uninstall_key', HostPackagesStatus.uninstall_key))
            migrate(*opes)

            (v, created) = ServerAttribs.get_or_create(key='db_version')
            v.value = next_version
            v.save()


if __name__ == '__main__':
    if platform.system() != 'Windows' and getpass.getuser() != 'wapt':
        print """you should run this program as wapt:
                     sudo -u wapt python /opt/wapt/waptserver/model.py  <action>
                 actions : init_db
                           upgrade2postgres"""
        sys.exit(1)

    usage = """\
    %prog [-c configfile] [action]

    WAPT Server database reset / init / upgrade.

    action is either :
       init_db: initialize or upgrade an existing DB without dropping data
       reset_db: initiliaze or recreate an empty database dropping the data.
    """
    parser = OptionParser(usage=usage, version=__version__)
    parser.add_option(
        '-c',
        '--config',
        dest='configfile',
        default=waptserver.config.DEFAULT_CONFIG_FILE,
        help='Config file full path (default: %default)')
    parser.add_option('-l','--loglevel',dest='loglevel',default=None,type='choice',
            choices=['debug',   'warning','info','error','critical'],
            metavar='LOGLEVEL',help='Loglevel (default: warning)')
    parser.add_option('-d','--devel',dest='devel',default=False,action='store_true',
            help='Enable debug mode (for development only)')


    (options, args) = parser.parse_args()
    conf = waptserver.config.load_config(options.configfile)
    load_db_config(conf)

    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s')


    if options.loglevel is not None:
        setloglevel(logger, options.loglevel)
    else:
        setloglevel(logger, conf['loglevel'])

    if len(args) == 1:
        action = args[0]
        if action == 'init_db':
            print ('initializing missing wapt tables without dropping data.')
            init_db(False)
            sys.exit(0)
        elif action == 'reset_db':
            print ('Drop existing tables and recreate wapt tables.')
            init_db(True)
            sys.exit(0)
    else:
        parser.print_usage()
