"""
Tests of the action manager following a run through its post-actions (#206), through `manage_actions` as Dash
dispatches it.

When a run completes, the manager creates the requests of its post-actions and sends them to the dispatcher. They have
no run until a worker claims them. The manager disabled its poll interval in the same call, as no run was under way,
so the completion of the post-actions was never handled: the tables of a DSA were never drawn, and their triggers
never set.
"""
from typing import Any, cast
from unittest import mock

from dash import dcc, html
import sqlalchemy as sa

# The plugins import the action callbacks, so are loaded first (by the base), as by the app
from .base import InputChangeTestCase, _Unused
from .dash_dispatch import NOT_UPDATED, CallbackResponse, dispatch_callback, get_callback_spec

from newsegsmodelapp import registers
from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db import read_transaction, write_transaction
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.backend.db.db_request_handler import FromDatabaseRequestHandler
from newsegsmodelapp.components.callbacks import action_callbacks
from newsegsmodelapp.dash_extension import NewsegsDash

POLL_ID = 'progress-poll-interval'
CONTAINER_ID = {'type': 'results-container', 'supersection': 'dsa', 'section': 'tabledraw'}

CHAIN = (
    ('run', 'dsa_run_metamodel'),
    ('postprocess', 'postproc_dsa_metamodel'),
    ('tabledraw', 'table_dsa_metamodel'),
)
"""The class and type of each request of a DSA of one configuration: the run, then its post-actions."""

def _trigger_id(section: str, key: str) -> dict:
    return {
        'type': 'postaction-trigger', 'purpose': 'trigger',
        'supersection': 'global', 'section': section, 'key': key, 'subindex': 0,
    }

class TestPostActionsFollowed(InputChangeTestCase):

    def setUp(self):
        super().setUp()
        from newsegsmodelapp.backend import db
        self.request_handler = FromDatabaseRequestHandler(db.get_engine)
        self.app = NewsegsDash(
            __name__,
            project_provider = self.provider,
            results_provider = cast(Any, _Unused()),
            request_handler = self.request_handler,
            suppress_callback_exceptions = True,
        )
        self.app.layout = html.Div()
        action_callbacks.add_action_callbacks(self.app)
        self.app.server.config['TESTING'] = True
        self.client = self.app.server.test_client()

        # Requests are sent to no dispatcher: the test does the work of the workers
        patcher = mock.patch.object(action_callbacks, 'send_to_dispatcher')
        self.sent = patcher.start()
        self.addCleanup(patcher.stop)

        # The store the manager keeps on the page
        self.ongoing_actions: list[int] = []
        self.n_polls = 0

    def complete_as_worker(self, request: registers.RunRequest) -> int:
        """Claim a request and complete its run, as a worker does; returns the id of the run"""
        run_id, _ = generate_claim_ticket(self.engine, request)
        with write_transaction(self.engine) as conn:
            conn.execute(
                sa.update(tbls.runs).where(tbls.runs.c.run_id == run_id).values(status = 'SUCCESS', progress = 1.)
            )
        return run_id

    def poll(self, triggers: tuple[tuple[str, str], ...] = CHAIN) -> CallbackResponse:
        """A tick of the poll interval, on a page with the post-action triggers of the (section, key) given"""
        self.n_polls += 1
        overlay = {'supersection': CONTAINER_ID['supersection'], 'section': CONTAINER_ID['section']}
        response = dispatch_callback(
            self.client,
            get_callback_spec(self.client, 'results-container', 'data-status'),
            trigger = POLL_ID, value = self.n_polls,
            components = [
                html.Div(id = CONTAINER_ID),
                html.Div(id = {'type': 'results-overlay-text', **overlay}),
                html.Div(id = {'type': 'results-overlay-subtext', **overlay}),
                html.Progress(id = {'type': 'results-progress-bar', **overlay}),
                *[dcc.Store(id = _trigger_id(section, key)) for section, key in triggers],
            ],
            stores = {'ongoing-actions': self.ongoing_actions, 'failed-actions': []},
        )
        ongoing = response.get('ongoing-actions', 'data')
        if ongoing is not NOT_UPDATED:
            self.ongoing_actions = ongoing
        return response

    def active_requests(self) -> dict[str, registers.RunRequest]:
        return {x.request_type: x for x in self.request_handler.get_active_requests()}

    def request_status(self, request_id: int) -> str:
        with read_transaction(self.engine) as conn:
            return conn.execute(
                sa.select(tbls.requests.c.status).where(tbls.requests.c.request_id == request_id)
            ).scalar_one()

    def test_polling_continues_until_the_tables_are_drawn(self):
        self.request_handler.add_request(CHAIN[0][1], self.project_id, self.provider, 'run')

        # The manager sends the run to the dispatcher, and waits for a worker
        response = self.poll()
        self.assertEqual(self.sent.call_count, 1)
        self.assertIs(response.get(POLL_ID, 'disabled'), False)
        self.assertEqual(response.get(CONTAINER_ID, 'data-status'), 'CALCULATING')

        # Each request completes before the next poll, which sets its trigger and creates the next request
        for i, (section, request_type) in enumerate(CHAIN):
            with self.subTest(completed = request_type):
                active = self.active_requests()
                self.assertEqual(list(active), [request_type])
                self.complete_as_worker(active[request_type])

                response = self.poll()

                self.assertIsNot(response.get(_trigger_id(section, request_type), 'data'), NOT_UPDATED)
                self.assertEqual(self.request_status(active[request_type].request_id), 'FULFILLED')
                if i + 1 < len(CHAIN):
                    # The next request has no run yet, but the manager must come back for it
                    self.assertEqual(list(self.active_requests()), [CHAIN[i + 1][1]])
                    self.assertEqual(self.sent.call_count, i + 2)
                    self.assertIs(response.get(POLL_ID, 'disabled'), False)
                    self.assertEqual(response.get(CONTAINER_ID, 'data-status'), 'CALCULATING')

        # Nothing is left to follow
        self.assertEqual(self.active_requests(), {})
        self.assertIs(response.get(POLL_ID, 'disabled'), True)
        self.assertEqual(response.get(CONTAINER_ID, 'data-status'), 'IDLE')

    def test_project_table_draw_redraws_the_tables_of_each_configuration(self):
        # The table draw of a whole-project DSA or PSA saves each configuration's tables too, shown in the
        # individual view, which has triggers of its own
        for analysis in ('dsa', 'psa'):
            with self.subTest(analysis = analysis):
                project, single, other = f'table_{analysis}_project', f'table_{analysis}_metamodel', 'table_net'
                self.request_handler.add_request(project, self.project_id, self.provider, 'tabledraw')
                self.complete_as_worker(self.active_requests()[project])

                response = self.poll(tuple(('tabledraw', x) for x in (project, single, other)))

                self.assertIsNot(response.get(_trigger_id('tabledraw', project), 'data'), NOT_UPDATED)
                self.assertIsNot(response.get(_trigger_id('tabledraw', single), 'data'), NOT_UPDATED)
                self.assertIs(response.get(_trigger_id('tabledraw', other), 'data'), NOT_UPDATED)

    def test_polling_stops_with_no_requests(self):
        response = self.poll()
        self.assertIs(response.get(POLL_ID, 'disabled'), True)
        self.assertEqual(response.get(CONTAINER_ID, 'data-status'), 'IDLE')
