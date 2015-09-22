# pylint: disable = missing-docstring
import base64

from saml2 import server, BINDING_HTTP_POST, BINDING_HTTP_REDIRECT
from saml2.authn_context import AuthnBroker, authn_context_class_ref, PASSWORD
from saml2.client import Saml2Client
from saml2.config import config_factory
from satosa.backends.base import BackendBase
from satosa.frontends.base import FrontendBase


class FakeSP(Saml2Client):
    def __init__(self, config_module):
        Saml2Client.__init__(self, config_factory('sp', config_module))

    def make_auth_req(self, entity_id):
        # Picks a binding to use for sending the Request to the IDP
        _binding, destination = self.pick_binding(
            'single_sign_on_service',
            [BINDING_HTTP_REDIRECT, BINDING_HTTP_POST], 'idpsso',
            entity_id=entity_id)
        # Binding here is the response binding that is which binding the
        # IDP shou  ld use to return the response.
        acs = self.config.getattr('endpoints', 'sp')[
            'assertion_consumer_service']
        # just pick one
        endp, return_binding = acs[0]

        req_id, req = self.create_authn_request(destination,
                                                binding=return_binding)
        ht_args = self.apply_binding(_binding, '%s' % req, destination,
                                     relay_state='hello')

        url = ht_args['headers'][0][1]
        return url


class FakeIdP(server.Server):
    def __init__(self, user_db):
        server.Server.__init__(self, 'configurations.idp_conf')
        self.user_db = user_db

    def handle_auth_req(self, saml_request, relay_state, binding, userid):
        auth_req = self.parse_authn_request(saml_request, binding)
        binding_out, destination = self.pick_binding(
            'assertion_consumer_service',
            entity_id=auth_req.message.issuer.text, request=auth_req.message)

        resp_args = self.response_args(auth_req.message)
        authn_broker = AuthnBroker()
        authn_broker.add(authn_context_class_ref(PASSWORD), lambda: None, 10,
                         'unittest_idp.xml')
        authn_broker.get_authn_by_accr(PASSWORD)
        resp_args['authn'] = authn_broker.get_authn_by_accr(PASSWORD)

        _resp = self.create_authn_response(self.user_db[userid],
                                           userid=userid,
                                           **resp_args)

        http_args = self.apply_binding(BINDING_HTTP_POST, '%s' % _resp,
                                       destination, relay_state, response=True)
        url = http_args['url']
        saml_response = base64.b64encode(str(_resp).encode("utf-8"))
        resp = {'SAMLResponse': saml_response, 'RelayState': relay_state}
        return url, resp


class FakeBackend(BackendBase):
    def __init__(self, start_auth_func=None, register_endpoints_func=None):
        super(FakeBackend, self).__init__(None)

        self.start_auth_func = start_auth_func
        self.register_endpoints_func = register_endpoints_func

    def start_auth(self, context, request_info, state):
        if self.start_auth:
            return self.start_auth(context, request_info, state)
        return None

    def register_endpoints(self):
        if self.register_endpoints_func:
            return self.register_endpoints_func()
        return None


class FakeFrontend(FrontendBase):
    def __init__(self, handle_authn_request_func=None, handle_authn_response_func=None,
                 register_endpoints_func=None):
        super(FakeFrontend, self).__init__(None)
        self.handle_authn_request_func = handle_authn_request_func
        self.handle_authn_response_func = handle_authn_response_func
        self.register_endpoints_func = register_endpoints_func

    def handle_authn_request(self, context, binding_in):
        if self.handle_authn_request_func:
            return self.handle_authn_request_func(context, binding_in)
        return None

    def handle_authn_response(self, context, internal_response, state):
        if self.handle_authn_response_func:
            return self.handle_authn_response_func(context, internal_response, state)
        return None

    def register_endpoints(self, providers):
        if self.register_endpoints_func:
            return self.register_endpoints_func(providers)
