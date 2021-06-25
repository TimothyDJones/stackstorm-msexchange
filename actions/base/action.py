from collections import namedtuple
import os

from st2common.runners.base_action import Action
from st2common.content import utils as content_utils
from st2client.client import Client
from st2client.models import KeyValuePair
from exchangelib import Account, ServiceAccount, Configuration, DELEGATE, EWSTimeZone

CacheEntry = namedtuple('CacheEntry', 'ews_url ews_auth_type primary_smtp_address')


class BaseExchangeAction(Action):
    def __init__(self, config):
        super(BaseExchangeAction, self).__init__(config)
        api_url = os.environ.get('ST2_ACTION_API_URL', None)
        token = os.environ.get('ST2_ACTION_AUTH_TOKEN', None)
        self.client = Client(api_url=api_url, token=token)
        self._credentials = ServiceAccount(
            username=config['username'],
            password=config['password'])
        self.timezone = EWSTimeZone.timezone(config['timezone'])
        try:
            server = config['server']
            autodiscover = False if server is not None else True
        except KeyError:
            autodiscover = True
        cache = self._get_cache()
        if cache:
            config = Configuration(
                service_endpoint=cache.ews_url,
                credentials=self._credentials,
                auth_type=cache.ews_auth_type)
            self.account = Account(
                primary_smtp_address=cache.primary_smtp_address,
                config=config,
                autodiscover=False,
                access_type=DELEGATE
            )
        else:
            if autodiscover:
                self.account = Account(
                    primary_smtp_address=config['primary_smtp_address'],
                    credentials=self._credentials,
                    autodiscover=autodiscover,
                    access_type=DELEGATE)
            else:
                ms_config = Configuration(
                    server=server,
                    credentials=self._credentials)
                self.account = Account(
                    primary_smtp_address=config['primary_smtp_address'],
                    config=ms_config,
                    autodiscover=False,
                    access_type=DELEGATE)
            self._store_cache_configuration()

        # Configure attachment parameters
        #self._attachment_configuration(config)

    def _store_cache_configuration(self):
        ews_url = self.account.protocol.service_endpoint
        ews_auth_type = self.account.protocol.auth_type
        primary_smtp_address = self.account.primary_smtp_address
        self.client.keys.update(KeyValuePair(name='exchange_ews_url',
            value=ews_url))
        self.client.keys.update(KeyValuePair(name='exchange_ews_auth_type',
            value=ews_auth_type))
        self.client.keys.update(KeyValuePair(name='exchange_primary_smtp_address',
            value=primary_smtp_address))

    def _get_cache(self):
        ews_url = self.client.keys.get_by_name(
            name='exchange_ews_url')
        ews_auth_type = self.client.keys.get_by_name(
            name='exchange_ews_auth_type')
        primary_smtp_address = self.client.keys.get_by_name(
            name='exchange_primary_smtp_address')
        if ews_url:
            return CacheEntry(
                ews_url=ews_url.value,
                ews_auth_type=ews_auth_type.value,
                primary_smtp_address=primary_smtp_address.value)
        else:
            return None

    def _attachment_configuration(self, config):
        attach_dir = config.get("attachment_directory", None)
        if not attach_dir:
            pack_name = getattr(self.action_service._action_wrapper,
                                "_pack", "unknown")
            pack_path = content_utils.get_pack_base_path(pack_name)
            attach_dir = os.path.join(pack_path, "attachments")
        else:
            attach_dir = os.path.abspath(attach_dir)

        # Create the folder/directory, if it doesn't exist,
        # and make it writeable.
        if not os.path.exists(attach_dir):
            os.makedirs(attach_dir, exist_ok=True)
            os.chmod(attach_dir, 0o755)
            self.logger.info("Created directory '{dir}' and made writeable."
                .format(dir=attach_dir))

        self._attachment_directory = attach_dir
        self._attachment_directory_max_size = config.get(
            "attachment_directory_maximum_size", 50)
        self._attachment_days_to_keep = config.get("attachment_days_to_keep", 7)
