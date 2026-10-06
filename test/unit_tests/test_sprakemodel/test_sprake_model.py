"""
Unit tests for newsegsmodel/sprakemodel.
"""
import os
import unittest
import json

import pandas as pd
import numpy as np
import numpy.testing

from config import settings

from newsegsmodelframework.util import jsonfuncs
from newsegsmodelframework.core import location
from newsegsmodelframework.newsegsmodel import sprakemodel
from newsegsmodelframework.newsegsfinance import sprakefinance
from newsegsmodelframework.newsegsgeneration import sprakegeneration
from newsegsmodelframework.newsegsgrid import sprakegrid
from newsegsmodelframework.newsegscs import sprakecs
from newsegsmodelframework.newsegsgeneration import newsegsgeneration
from newsegsmodelframework.newsegscs import newsegscs

class TestSprakeModelConfigEqualities(unittest.TestCase):
    """
    Tests for creating, serialising and restoring the model config.

    Running and results not considered in this test suite.
    """

    def test_basic_construction(self):
        mdl = sprakemodel.SprakeModel.from_none()
        self.assertIsInstance(mdl.generation, sprakegeneration.SprakeGeneration)
        self.assertIsInstance(mdl.grid, sprakegrid.SprakeGrid)
        self.assertIsInstance(mdl.consumption_storage, sprakecs.SprakeCS)

        mdl.generation.generator.generators[0].set_nameplate_capacity(200.)
        mdl.generation.generator.generators[1].set_nameplate_capacity(0.)
        self.assertEqual(mdl.generation.generator.nameplate_capacity, 200)
    
    def test_copy_construction(self):
        mdl = sprakemodel.SprakeModel.from_none()
        mdl.generation.wind_capacity = 200.
        mdl.generation.pv_capacity = 0.
        mdl.grid.import_rate = 0.5
        mdl.consumption_storage.efficiency_reduction = 0.5

        mdl2 = sprakemodel.SprakeModel(mdl)
        self.assertEqual(
            mdl.generation.generator.nameplate_capacity,
            mdl2.generation.generator.nameplate_capacity
        )
        self.assertEqual(
            mdl.grid.import_rate,
            mdl2.grid.import_rate
        )
        self.assertDictEqual(
            mdl.consumption_storage.get_appliance_params(),
            mdl2.consumption_storage.get_appliance_params()
        )
    
    def test_serialisation(self):
        mdl = sprakemodel.SprakeModel.from_none()
        mdl.generation.wind_capacity = 200.
        mdl.generation.pv_capacity = 0.
        mdl.grid.import_rate = 0.5
        mdl.consumption_storage.efficiency_reduction = 0.5

        # Use the without component server form
        d1 = mdl.to_dict_repr()

        mdl2 = sprakemodel.SprakeModel.from_dict(d1)

        self.assertEqual(
            mdl.generation.generator.nameplate_capacity,
            mdl2.generation.generator.nameplate_capacity
        )
        self.assertEqual(
            mdl.grid.import_rate,
            mdl2.grid.import_rate
        )
        self.assertDictEqual(
            mdl.consumption_storage.get_appliance_params(),
            mdl2.consumption_storage.get_appliance_params()
        )
    
    def test_json_serialisation(self):
        mdl = sprakemodel.SprakeModel.from_none()
        mdl.generation.wind_capacity = 200.
        mdl.generation.pv_capacity = 0.
        mdl.grid.import_rate = 0.5
        mdl.consumption_storage.efficiency_reduction = 0.5

        sd1 = mdl.json_dumps_repr()
        d2 = json.loads(sd1)

        mdl2 = sprakemodel.SprakeModel.from_dict(d2)

        self.assertEqual(
            mdl.generation.generator.nameplate_capacity,
            mdl2.generation.generator.nameplate_capacity
        )
        self.assertEqual(
            mdl.grid.import_rate,
            mdl2.grid.import_rate
        )
        self.assertDictEqual(
            mdl.consumption_storage.get_appliance_params(),
            mdl2.consumption_storage.get_appliance_params()
        )

class TestSprakeModelRun(unittest.TestCase):
    """
    Tests for basic operation of model run.
    """

    def test_default_run(self):
        mdl = sprakemodel.SprakeModel.from_none()
        #self.assertTrue(mdl.dirty)
        mdl.run()
        #self.assertFalse(mdl.dirty)
        self.assertIsInstance(
            mdl.get_generation_result(),
            sprakegeneration.SprakeGenerationResult
        )
        self.assertIsInstance(
            mdl.get_grid_result(),
            sprakegrid.SprakeGridResult
        )
        self.assertIsInstance(
            mdl.get_cs_result(),
            sprakecs.SprakeCSResult
        )
    
    def test_post_serialisation_run_stability(self):
        mdl = sprakemodel.SprakeModel.from_none()
        mdl.generation.wind_capacity = 200.
        mdl.generation.pv_capacity = 50.
        mdl.grid.import_rate = 0.5
        mdl.consumption_storage.efficiency_reduction = 0.5
        mdl.run()

        gen_meters_1 = mdl.get_generation_result().meters_to_pandas()
        cs_meters_1 = mdl.get_consumption_storage_result().meters_to_pandas()

        sd1 = mdl.json_dumps_repr()
        d2 = json.loads(sd1)

        mdl2 = sprakemodel.SprakeModel.from_dict(d2)
        mdl2.run()
        numpy.testing.assert_array_equal(
            gen_meters_1.to_numpy(),
            mdl2.get_generation_result().meters_to_pandas().to_numpy()
        )
        numpy.testing.assert_array_equal(
            cs_meters_1.to_numpy(),
            mdl2.get_consumption_storage_result().meters_to_pandas().to_numpy()
        )
    
    def test_excel_validation(self):
        """
        Internal validation using an independently coded excel model.

        Considers only the meters, not the financial estimates.
        """
        external_meter_data = (
            pd.read_excel(
                os.path.join(settings.get('SprakeExcelValidationLoc'), 'Sprake_model_validation.xlsx'),
                sheet_name = 'Raw',
                header = 0,
                parse_dates = ['datetime']
            )
            .assign(datetime = lambda df: df['datetime'].dt.tz_localize('utc'))
            .set_index('datetime')
        )

        with open(f'{os.getenv("PROJECT_ROOT_PATH")}/data/sprakemodel-validation-config.json', 'r') as f:
            d1 = json.load(f)
        
        mdl = sprakemodel.SprakeModel.from_dict(d1)
        mdl.run()

        gen_meters = newsegsgeneration.get_generation_meters(
            mdl.get_generation_result()
        )

        for colname in ['wind_export']:
            numpy.testing.assert_allclose(
                gen_meters[colname], 
                external_meter_data[colname],
                rtol = 1e-6,
                err_msg = 'Almost equal failure for `{0}`'.format(colname)
            )

        # For now, we accept that we have some numeric differences in solar
        for colname in ['solar_export']:
            numpy.testing.assert_allclose(
                gen_meters[colname], 
                external_meter_data[colname],
                atol = 0.01,
                rtol = 1e-2,
                err_msg = 'Almost equal failure for `{0}`'.format(colname)
            )

        cons_meters = newsegscs.get_consumption_meters(
            mdl.get_consumption_storage_result()
        )

        for colname in ['appliance_import', 'dhw_import', 'spaceheat_import', 'evcharge_import']:
            numpy.testing.assert_array_almost_equal(
                cons_meters[colname], 
                external_meter_data[colname],
                err_msg = 'Almost equal failure for `{0}`'.format(colname)
            )

class TestSprakeFinanceRun(unittest.TestCase):
    """
    Primarily for performing validation on the finance configuration.
    """

    def test_excel_validation(self):

        # Acceptable relative tolerance for validation
        RTOL = 1e-6

        external_finance_data = (
            pd.read_excel(
                os.path.join(settings.get('SprakeExcelValidationLoc'), 'Sprake_model_validation.xlsx'),
                sheet_name = 'Totals',
                header = 0,
                index_col = 'name'
            )
        )

        with open(f'{os.getenv("PROJECT_ROOT_PATH")}/data/sprakemodel-validation-config.json', 'r') as f:
            d1 = json.load(f)

        with open(f'{os.getenv("PROJECT_ROOT_PATH")}/data/sprakemodel-validation-finance-config.json', 'r') as f:
            fd1 = json.load(f)
        
        mdl = sprakemodel.SprakeModel.from_dict(d1)
        mdl.run()

        fnc = sprakefinance.SprakeFinance.from_dict(fd1)
        fnc.model = mdl

        numpy.testing.assert_allclose(
            fnc.get_total_present_costs_undiscounted(),
            float(external_finance_data.loc['total_cost_undiscounted', 'value']), # pyright: ignore[reportArgumentType]
            rtol = RTOL
        )

        numpy.testing.assert_allclose(
            fnc.get_total_present_costs_discounted(),
            float(external_finance_data.loc['total_cost_discounted', 'value']), # pyright: ignore[reportArgumentType]
            rtol = RTOL
        )

        numpy.testing.assert_allclose(
            fnc.get_total_present_benefits_undiscounted(),
            float(external_finance_data.loc['total_benefits_undiscounted', 'value']), # pyright: ignore[reportArgumentType]
            rtol = RTOL
        )

        numpy.testing.assert_allclose(
            fnc.get_total_present_benefits_discounted(),
            float(external_finance_data.loc['total_benefits_discounted', 'value']), # pyright: ignore[reportArgumentType]
            rtol = RTOL
        )

        numpy.testing.assert_allclose(
            fnc.get_net_present_value_undiscounted(),
            float(external_finance_data.loc['npv_undiscounted', 'value']), # pyright: ignore[reportArgumentType]
            rtol = 10*RTOL
        )

        numpy.testing.assert_allclose(
            fnc.get_net_present_value_discounted(),
            float(external_finance_data.loc['npv_discounted', 'value']), # pyright: ignore[reportArgumentType]
            rtol = 10*RTOL
        )
