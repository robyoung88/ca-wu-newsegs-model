"""
Uploading a configuration file (#169), through the upload callback of the configuration selector as Dash dispatches it.

A configuration is exported as `metamodel_to_config_file` does, encoded with `NumpyEncoder` as the download is, and
uploaded. Restoring the metamodel from the file left its variables a plain dict, so saving it failed with
`AttributeError: 'dict' object has no attribute '_syncronise'`.
"""
import base64
import json
from pathlib import Path
from typing import cast

from dash import dcc, html

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components.configuration_selector import add_configuration_selector_callbacks
from newsegsmodelapp.components.export import metamodel_to_config_file
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.core.trackeddata import TableModifyingObservableOrderedDict
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsvariable.variable import variable_uid
from newsegsmodelframework.util import jsonfuncs

from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

from .base import MODEL_TYPE, InputChangeTestCase
from .dash_dispatch import DEPENDENCIES_URL, CallbackSpec, dispatch_callback

UPLOAD_ID = {'type': 'config-upload', 'index': 0}

def file_contents(config: dict) -> str:
    """The contents of an uploaded file, as `dcc.Upload` gives them"""
    text = json.dumps(config, cls = jsonfuncs.NumpyEncoder, sort_keys = False, indent = 4)
    return 'data:application/json;base64,' + base64.b64encode(text.encode('utf-8')).decode('ascii')

class TestConfigUpload(InputChangeTestCase):

    def setUp(self):
        super().setUp()
        self.app = NewsegsDash(
            __name__,
            project_provider = self.provider,
            results_provider = None, # pyright: ignore[reportArgumentType]
            request_handler = None, # pyright: ignore[reportArgumentType]
            suppress_callback_exceptions = True,
        )
        self.app.layout = html.Div()
        add_configuration_selector_callbacks(self.app)
        self.app.server.config['TESTING'] = True
        self.client = self.app.server.test_client()

        # Settings which the file must carry
        proj = self.reader.get_project(self.project_id)
        mm = cast(NewsegsMetaModel, proj.metamodels[0])
        mm.optim_config.method = 'Powell'
        var = next(x for x in mm.variables.values() if x.optim_possible and x.optim_selectable)
        var.optim_selected = True
        var.optim_min = 5.
        var.optim_max = 500.
        var.optim_plot_intervals = 15
        self.optim_varid = variable_uid(var)
        self.reader.upsert_component(proj)

        source = cast(NewsegsMetaModel, self.reader.get_project(self.project_id).metamodels[0])
        self.source_name = source.name
        self.n_variables = len(source.variables)
        # Exported and decoded as a download is
        self.config = json.loads(json.dumps(metamodel_to_config_file(source), cls = jsonfuncs.NumpyEncoder))

    def upload(self, config: dict, project_id: str | None = None):
        """Upload a file to a project, through the upload callback"""
        # The callback's output is a store, so it is found by its input
        specs = [CallbackSpec.from_dependency(x) for x in self.client.get(DEPENDENCIES_URL).get_json()]
        spec = next(x for x in specs if any(isinstance(i, dict) and i.get('type') == 'config-upload' for i, _ in x.inputs))
        return dispatch_callback(
            self.client, spec, trigger = UPLOAD_ID, value = file_contents(config),
            components = [dcc.Upload(id = UPLOAD_ID)],
            stores = {'active-project-id': project_id or self.project_id},
        )

    def reloaded(self, project_id: str | None = None):
        """The project as a new process would load it"""
        from newsegsmodelapp.backend import db
        return FromDatabaseNewsegsProjectProvider(db.get_engine).get_project(project_id or self.project_id)

    def test_upload_saved(self):
        response = self.upload(self.config)
        self.assertEqual(response.get('active-project-id', 'data'), self.project_id)

        proj = self.reloaded()
        self.assertEqual(len(proj.metamodels), 2)
        uploaded = cast(NewsegsMetaModel, proj.metamodels[1])
        # Focussed, and named uniquely
        self.assertEqual(proj.get_focussed_metamodel().id, uploaded.id)
        self.assertNotEqual(uploaded.name, self.source_name)
        self.assertEqual(len({x.name for x in proj.metamodels}), 2)

        self.assertIsInstance(uploaded.variables, TableModifyingObservableOrderedDict)
        self.assertEqual(len(uploaded.variables), self.n_variables)
        self.assertEqual(uploaded.optim_config.method, 'Powell')
        var = uploaded.variables[self.optim_varid]
        self.assertEqual((var.optim_min, var.optim_max, var.optim_plot_intervals), (5., 500., 15))
        self.assertTrue(var.optim_selected)

        uploaded.model.run()
        uploaded.finance.run()
        self.assertIsNotNone(uploaded.model.get_generation_result())

    def test_file_without_optimisation_settings(self):
        # As exported from main, before the metamodel held its optimisation settings
        config = json.loads(json.dumps(self.config))
        config['metamodel'].pop('_optim_config')
        config['metamodel'].pop('version', None)
        self.upload(config)
        uploaded = cast(NewsegsMetaModel, self.reloaded().metamodels[1])
        self.assertEqual(uploaded.optim_config.method, 'Nelder-Mead')
        self.assertEqual(len(uploaded.variables), self.n_variables)

    # An uploaded configuration is independent of the configuration it was exported from: its variables have new
    # ids, so the upload doesn't overwrite them, and editing it changes no other configuration, in any project.

    KEY = 'gen_input.wind_capacity.0'

    def edit(self, project_id: str, mm_index: int, value: float):
        from newsegsmodelapp.backend import db
        provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        var = provider.get_project(project_id).metamodels[mm_index].variables[self.KEY]
        var.set_parameters(value)
        provider.variable_provider.upsert_variable([var], force = True)

    def values(self, project_id: str | None = None) -> list:
        return [mm.variables[self.KEY].parameters[0] for mm in self.reloaded(project_id).metamodels]

    def test_into_the_same_project(self):
        source_ids = {v.id for v in self.reloaded().metamodels[0].variables.values()}
        self.upload(self.config)
        uploaded = self.reloaded().metamodels[1]
        self.assertFalse(source_ids & {v.id for v in uploaded.variables.values()})

        self.edit(self.project_id, 1, 99.)
        self.assertEqual(self.values(), [50., 99.])

    def test_an_older_file_leaves_the_original(self):
        # The original is edited after the export
        self.edit(self.project_id, 0, 57.)
        self.upload(self.config)
        self.assertEqual(self.values(), [57., 50.])

    def test_into_another_project(self):
        other = PROJECT_FACTORIES[MODEL_TYPE]()
        self.reader.add_component(other)
        self.upload(self.config, project_id = other.id)

        uploaded = self.reloaded(other.id).metamodels[1]
        project_ids = {v.id for mm in self.reloaded().metamodels for v in mm.variables.values()}
        self.assertFalse(project_ids & {v.id for v in uploaded.variables.values()})

        self.edit(other.id, 1, 150.)
        self.assertEqual(self.values(), [50.])
        self.assertEqual(self.values(other.id), [50., 150.])

    def test_twice(self):
        self.upload(self.config)
        self.upload(self.config)
        proj = self.reloaded()
        self.assertEqual(len(proj.metamodels), 3)
        self.assertEqual(len({mm.name for mm in proj.metamodels}), 3)
        ids = [{v.id for v in mm.variables.values()} for mm in proj.metamodels]
        self.assertFalse(ids[1] & ids[2])

        self.edit(self.project_id, 2, 99.)
        self.assertEqual(self.values(), [50., 50., 99.])

    def test_file_exported_from_main(self):
        # Exported by the download of main (a9ea019), before the metamodel held its optimisation settings
        path = Path(__file__).parent / 'data' / 'config_exported_from_main.json'
        config = json.loads(path.read_text(encoding = 'utf-8'))
        self.assertNotIn('_optim_config', config['metamodel'])

        self.upload(config)
        uploaded = cast(NewsegsMetaModel, self.reloaded().metamodels[1])
        self.assertIsInstance(uploaded.variables, TableModifyingObservableOrderedDict)
        self.assertEqual(len(uploaded.variables), len(config['metamodel']['_variables']))
        self.assertEqual(uploaded.optim_config.method, 'Nelder-Mead')
        uploaded.model.run()
        uploaded.finance.run()
        self.assertIsNotNone(uploaded.finance.get_net_present_value_discounted())
