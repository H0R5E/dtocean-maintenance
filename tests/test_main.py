# -*- coding: utf-8 -*-
"""
Created on Wed Sep 06 14:44:04 2017

@author: mtopper
"""

import pytest

import pandas as pd

from dtocean_maintenance.input import inputOM
from dtocean_maintenance.main import LCOE_Statistics


@pytest.fixture
def data_point():
    
    data_point = {"lifetimeOpex [Euro]": 10674780.0,
                  "lifetimeEnergy [Wh]": 139850176684.0,
                  "LCOEOpex [Euro/kWh]": 0.15,
                  "arrayDowntime [hour]": 73824.0,
                  "arrayAvailability [-]": 0.578920950713,
                  "numberOfJourneys [-]": 15,
                  "CapexOfArray [Euro]": 1.,
                  "OpexPerYear [Euro]": pd.DataFrame(
                        {'Cost': {0: 0.0,
                                  1: 10287391.0,
                                  2: 0.0,
                                  3: 0.0,
                                  4: 0.0,
                                  5: 0.0,
                                  6: 0.0,
                                  7: 162760.0,
                                  8: 0.0,
                                  9: 0.0,
                                  10: 0.0,
                                  11: 0.0,
                                  12: 224629.0,
                                  13: 0.0,
                                  14: 0.0,
                                  15: 0.0,
                                  16: 0.0,
                                  17: 0.0,
                                  18: 0.0,
                                  19: 0.0,
                                  20: 0.0,
                                  21: 0.0},
                         'Year': {0: 0,
                                  1: 1,
                                  2: 2,
                                  3: 3,
                                  4: 4,
                                  5: 5,
                                  6: 6,
                                  7: 7,
                                  8: 8,
                                  9: 9,
                                  10: 10,
                                  11: 11,
                                  12: 12,
                                  13: 13,
                                  14: 14,
                                  15: 15,
                                  16: 16,
                                  17: 17,
                                  18: 18,
                                  19: 19,
                                  20: 20,
                                  21: 21}}),
                  "energyPerYear [Wh]": pd.DataFrame(
                        {'Energy': {0: 0.0,
                                    1: 14439780677.519999,
                                    2: 12419999875.799999,
                                    3: 12419999875.799999,
                                    4: 12419999875.799999,
                                    5: 12454027272.719999,
                                    6: 12419999875.799999,
                                    7: 7419205405.2600002,
                                    8: 12019890290.76,
                                    9: 12093040974.959999,
                                    10: 12059999879.4,
                                    11: 12059999879.4,
                                    12: 7624232800.4699993,
                                    13: 0.0,
                                    14: 0.0,
                                    15: 0.0,
                                    16: 0.0,
                                    17: 0.0,
                                    18: 0.0,
                                    19: 0.0,
                                    20: 0.0,
                                    21: 0.0},
                         'Year': {0: 0,
                                  1: 1,
                                  2: 2,
                                  3: 3,
                                  4: 4,
                                  5: 5,
                                  6: 6,
                                  7: 7,
                                  8: 8,
                                  9: 9,
                                  10: 10,
                                  11: 11,
                                  12: 12,
                                  13: 13,
                                  14: 14,
                                  15: 15,
                                  16: 16,
                                  17: 17,
                                  18: 18,
                                  19: 19,
                                  20: 20,
                                  21: 21}}),
                  "downtimePerDevice [hour]": {'device001': 74009.0,
                                               'device002': 122204.0,
                                               'device003': 129879.0},
                  "energyPerDevice [Wh]": {'device001': 72861369134.400009,
                                           'device002': 37109136615.210007,
                                           'device003': 29879670934.079998},
                  'eventTables [-]': None
                  }
                  
    return data_point


@pytest.fixture
def logistics_param():
    
    logistics_param = {"metocean": None}
                  
    return logistics_param


def test_LCOE_Statistics_main(mocker, data_point, logistics_param):
    
    mocker.patch('dtocean_maintenance.main.LCOE_Calculator.__init__',
                 return_value=None)
    mocker.patch('dtocean_maintenance.main.LCOE_Calculator.executeCalc',
                 return_value=data_point)
    mocker.patch('dtocean_logistics.performance.schedule.schedule_shared.'
                 'WaitingTime.__init__',
                 return_value=None)
    n_sims = 5
    control = inputOM(None,
                      None,
                      None,
                      None,
                      None,
                      None,
                      logistics_param,
                      None,
                      {'numberOfSimulations': n_sims})
    
    test = LCOE_Statistics(control)
    result = test.main()
    keys = ["MetricsTable [-]",
            "OpexPerYear [Euro]",
            "energyPerYear [Wh]",
            "downtimePerDevice [hour]",
            "energyPerDevice [Wh]",
            'eventTables [-]',
            "CapexOfArray [Euro]"]
        
    assert set(result.keys()) == set(keys)
    assert len(result["OpexPerYear [Euro]"].columns) == n_sims
    assert len(result['energyPerYear [Wh]'].columns) == n_sims
    assert len(result["OpexPerYear [Euro]"]) == 22
    assert len(result['energyPerYear [Wh]']) == 22
    assert len(result["downtimePerDevice [hour]"].columns) == n_sims
    assert len(result["energyPerDevice [Wh]"].columns) == n_sims
    assert len(result["downtimePerDevice [hour]"]) == 3
    assert len(result["energyPerDevice [Wh]"]) == 3
    
    
def test_LCOE_Statistics_main_no_sims(mocker, data_point, logistics_param):
    
    mocker.patch('dtocean_maintenance.main.LCOE_Calculator.__init__',
                 return_value=None)
    mocker.patch('dtocean_maintenance.main.LCOE_Calculator.executeCalc',
                 return_value=data_point)
    mocker.patch('dtocean_logistics.performance.schedule.schedule_shared.'
                 'WaitingTime.__init__',
                 return_value=None)
    n_sims = 0
    control = inputOM(None,
                      None,
                      None,
                      None,
                      None,
                      None,
                      logistics_param,
                      None,
                      {'numberOfSimulations': n_sims})
    
    test = LCOE_Statistics(control)
    
    with pytest.raises(ValueError):
        test.main()
    
    
def test_LCOE_Statistics_call(mocker, data_point, logistics_param):
    
    mocker.patch('dtocean_maintenance.main.LCOE_Calculator.__init__',
                 return_value=None)
    mocker.patch('dtocean_maintenance.main.LCOE_Calculator.executeCalc',
                 return_value=data_point)
    mocker.patch('dtocean_logistics.performance.schedule.schedule_shared.'
                 'WaitingTime.__init__',
                 return_value=None)    
    n_sims = 5
    control = inputOM(None,
                      None,
                      None,
                      None,
                      None,
                      None,
                      logistics_param,
                      None,
                      {'numberOfSimulations': n_sims})
    
    test = LCOE_Statistics(control)
    test()
    
    assert True
