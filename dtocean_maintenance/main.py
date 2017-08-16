# -*- coding: utf-8 -*-
"""This module contains the main classes of dtocean-maintenance

.. moduleauthor:: Bahram Panahandeh <bahram.panahandeh@iwes.fraunhofer.de>
                  Mathew Topper <dataonlygreater@gmail.com>
"""

# Standard modules
import sys
import copy
import math
import string
import timeit
import logging
import datetime
from datetime import timedelta

# 3rd party modules
import numpy as np
import pandas as pd

# DTOcean modules
from dtocean_logistics.feasibility.feasability_om import feas_om
from dtocean_logistics.load.safe_factors import safety_factors
from dtocean_logistics.phases import select_port_OM
from dtocean_logistics.phases.om import logPhase_om_init
from dtocean_logistics.phases.om.select_logPhase import logPhase_select
from dtocean_logistics.phases.operations import logOp_init
from dtocean_logistics.selection.select_ve import select_e, select_v
from dtocean_logistics.selection.match import compatibility_ve
from dtocean_reliability.main import Variables, Main

# Internal modules
from .array import Array
from .logistics import om_logistics_main
from .static import poissonProcess

# Set up logging
module_logger = logging.getLogger(__name__)


class LCOE_Optimiser(object):

    def __init__(self, inputOMPtr):

        '''__init__ function: init function of LCOE_Optimiser: entry class of
        dtocean-maintenance module

        Args:
            inputOMPtr (class): pointer of class inputOM

        Attributes:
            self.__calcPTR (class): Instance pointer of LCOE_Calculator
            self.__inputOMPTR (class): Instance pointer of inputOM
            self.__outputsOfWP6 (dict): Dictionary which contains the outputs
              of WP6, Optimised LCOE of array [€/kWh], AnnualEnergyOfArray
              [MWh] etc.

        Returns:
            no returns

        '''

        # Instance pointer of LCOE_Calculator
        self.__calcPTR = None

        # Instance pointer of inputOM
        self.__inputOMPTR = inputOMPtr

        # output of WP6
        self.__outputsOfWP6 = {}

        # Make an instance of LCOE_Calculator
        self.__makeInstance()

        return

    def __makeInstance(self):

        '''__makeInstance function: makes an instance of class LCOE_Calculator.

        Args:
            no arguments

        Attributes:
            self.__calcPTR (calss): Instance pointer of LCOE_Calculator

        Returns:
            no returns

        '''

        self.__calcPTR = LCOE_Calculator(self.__inputOMPTR)

        return

    def __call__(self):

        '''__call__ function: call function

        Args:
            no arguments

        Attributes:
            no attributs

        Returns:
            self.__outputsOfWP6 (dict): Output of WP6

        '''

        self.executeOptim()

        return self.__outputsOfWP6


    def executeOptim(self):

        '''executeOptim function: calls LCOE_Calculator for the calculation of
        LCOE

        Args:
            no arguments

        Attributes:
            self.__outputsOfWP6 (dict): Output of WP6

        Returns:
            self.__outputsOfWP6 (dict): Output of WP6

        '''

        # the optimisation algorithm will be implemented here in a loop
        try:

            self.__outputsOfWP6 = self.__calcPTR.executeCalc()

        except KeyboardInterrupt:

            sys.exit('Interrupt by Keyboard in dtocean_maintenance')

        return self.__outputsOfWP6


class LCOE_Calculator(object):

    '''Cost calculation class of dtocean-operations-and-maintenance.

    Attributes:
        self.__inputOMPTR (class): pointer of inputOM class
        self.__Farm_OM (dict): This parameter records the O&M general
            information for the farm as whole
            keys:
                calendar_based_maintenance (bool) [-]:
                    User input if one wants to consider calendar based
                    maintenance
                condition_based_maintenance (bool) [-]:
                    User input if one wants to consider condition based
                    maintenance
                corrective_maintenance (bool) [-]:
                    User input if one wants to consider corrective maintenance
                duration_shift (int) [h]:
                    Duration of a shift
                helideck (str or bool -> logistic) [-]:
                    If there is helideck available or not?
                number_crews_available (int) [-]:
                    Number of available crews
                number_crews_per_shift (int) [-]:
                    Number of crews per shift
                number_shifts_per_day (int) [-]:
                    Number of shifts per day
                wage_specialist_day (float) [Euro/h]:
                    Wage for specialists crew at daytime e.g. diver
                wage_specialist_night (float) [Euro/h]:
                    Wage for specialists crew at night time e.g. diver
                wage_technician_day (float) [Euro/h]:
                    Wage for technicians at daytime
                wage_technician_night (float) [Euro/h]:
                    Wage for technicians at night time
                workdays_summer (int) [-]:
                    Working Days per Week during summer
                workdays_winter (int) [-]:
                    Working Days per Week during winter
                energy_selling_price (float) [Euro/kWh]:
                    Energy selling price

        self.__Component (Pandas DataFrame): This table stores information
            related to the components. A component is any physical object
            required during the operation of the farm.
            keys:
                component_id (str) [-]:
                    Id of components
                component_type (str) [-]:
                    Type of components
                component_subtype: (str) [-]:
                    sub type of components
                failure_rate (float) [1/year]:
                    Failure rate of the components
                number_failure_modes (int) [-]:
                    Number of failure modes for this component
                start_date_calendar_based_maintenance (datetime) [-]:
                    Start date of calendar-based maintenance for each year
                end_date_calendar_based_maintenance	 (datetime)	[-]:
                    End date of calendar-based maintenance for each year
                interval_calendar_based_maintenance	int (year) [-]:
                    Interval of calendar-based maintenance
                start_date_condition_based_maintenance (datetime) [-]:
                    Start date of condition-based maintenance for each year
                end_date_condition_based_maintenance (datetime) [-]:
                    End date of condition-based maintenance
                soh_threshold (float) [-]:
                    This parameter belongs to condition based strategy
                is_floating	(bool) [-]:
                    Component is floating and can be towed to port

        self.__Failure_Mode (Pandas DataFrame): This table stores information
            related to the failure modes of components
            keys:
                component_id (str) [-]:
                    Id of component
                fm_id (str) [-]:
                    Id of failure mode
                mode_probability (float) [%]:
                    Probability of occurrence of each failure modes
                spare_mass (float) [kg]:
                    Mass of the spare parts
                spare_height	 (float)	[m]:
                    Height of the spare parts
                spare_width	int (float) [m]:
                    Width of the spare parts
                spare_length (float) [m]:
                    Length of the spare parts
                cost_spare (float) [Euro]:
                    Cost of the spare parts
                cost_spare_transit	(float) [Euro]:
                    Cost of the transport of the spare parts
                cost_spare_loading	(float) [Euro]:
                    Cost of the loading of the spare parts
                lead_time_spare	(bool) [days]:
                    Lead time for the spare parts

        self.__Repair_Action (Pandas DataFrame): This table stores information
        related to the repair actions required for each failure modes
            keys:
                component_id (str) [-]:
                    Id of component
                fm_id (str) [-]:
                    Id of failure mode
                duration_maintenance (float) [h]:
                    Duration of time required on site for maintenance
                duration_accessibility (float) [h]:
                    Duration of time required on site to access the component
                    or sub-systems to be repaired or replaced
                interruptable (bool) [-]:
                    Is the failure mode type interruptable or not
                delay_crew (float) [h]:
                    duration of time before the crew is ready
                delay_organisation (float) [h]:
                    duration of time before anything else is ready
                delay_spare	(float) [h]:
                    duration of time before the spare parts are ready
                number_technicians (int) [-]:
                    Number of technicians required to do the O&M
                number_specialists (int) [-]:
                    Number of specialists required to do the O&M
                wave_height_max_acc (float) [m]:
                    wave height max for operational limit conditions during
                    the accessibility
                wave_periode_max_acc (float) [s]:
                    wave period max for operational limit conditions during
                    the accessibility
                wind_speed_max_acc (float) [m/s]:
                    wind speed max for operational limit conditions during the
                    accessibility
                current_speed_max_acc (float) [m/s]:
                    current speed max for operational limit conditions during
                    the accessibility
                wave_height_max_om (float) [m]:
                    wave height max for operational limit conditions during
                    the maintenance action
                wave_periode_max_om (float) [s]:
                    wave period max for operational limit conditions during
                    the maintenance action
                wind_speed_max_om	 (float) [m/s]:
                    wind speed max for operational limit conditions during the
                    maintenance action
                current_speed_max_om (float) [m/s]:
                    current speed max for operational limit conditions during
                    the maintenance action
                requires_lifiting	 (bool) [-]:
                    Is lifting required?
                requires_divers (bool) [-]:
                    Are divers required?
                requires_towing (bool) [-]:
                    Is towing required?

        self.__Inspection (Pandas DataFrame): This table stores information
            related to the inspections required for each failure modes
            keys:
                component_id (str) [-]:
                    Id of component
                fm_id (str) [-]:
                    Id of failure mode
                duration_inspection (float) [h]:
                    Duration of time required onsite for inspection
                duration_accessibility (float) [h]:
                    Duration of time required on site to access the component
                    or sub-systems to be repaired or replaced
                delay_crew (float) [h]:
                    duration of time before the crew is ready
                delay_organisation (float) [h]:
                    duration of time before anything else is ready
                number_technicians (int) [-]:
                    Number of technicians required to do the O&M
                number_specialists (int) [-]:
                    Number of specialists required to do the O&M
                wave_height_max_acc (float) [m]:
                    Wave height max for operational limit conditions during
                    the accessibility
                wave_periode_max_acc (float) [s]:
                    Wave period max for operational limit conditions during
                    the accessibility
                wind_speed_max_acc (float) [m/s]:
                    Wind speed max for operational limit conditions during the
                    accessibility
                current_speed_max_acc (float) [m/s]:
                    Current speed max for operational limit conditions during
                    the accessibility
                wave_height_max_om (float) [m]:
                    Wave height max for operational limit conditions during
                    the maintenance action
                wave_periode_max_om (float) [s]:
                    Wave period max for operational limit conditions during
                    the maintenance action
                wind_speed_max_om	 (float) [m/s]:
                    Wind speed max for operational limit conditions during the
                    maintenance action
                current_speed_max_om (float) [m/s]:
                    Current speed max for operational limit conditions during
                    the maintenance action
                requires_lifiting	 (bool) [-]:
                    Is lifting required?
                requires_divers (bool) [-]:
                    Are divers required?


        self.__RAM_Param (dict): This parameter records the information for
        talking to RAM module
            keys:
                calcscenario (str) [-]: scenario for the calculation
                eleclayout (str) [-]: Electrical layout architecture
                pointer (class) [-]: pointer of dtocean-reliability class
                severitylevel (str) [-]: Level of severity
                systype (str) [-]: Type of system

        self.__Logistic_Param (dict): This parameter records the information
        for talking to logistic module
            keys:
                cable_route (DataFrame): logistic parameter
                collection_point (DataFrame): logistic parameter
                connerctors (DataFrame): logistic parameter
                device (DataFrame): logistic parameter
                dynamic_cable (DataFrame): logistic parameter
                equipments (dict): logistic parameter
                external_protection (DataFrame): logistic parameter
                foundation (DataFrame): logistic parameter
                landfall (DataFrame): logistic parameter
                laying_rates (DataFrame): logistic parameter
                layout (DataFrame): logistic parameter
                lease_area (list): logistic parameter
                line (DataFrame): logistic parameter
                metocean (DataFrame): logistic parameter
                other_rates (DataFrame): logistic parameter
                penet_rates (DataFrame): logistic parameter
                ports (DataFrame): logistic parameter
                schedule_OLC (DataFrame): logistic parameter
                site (DataFrame): logistic parameter
                static_cable (DataFrame): logistic parameter
                sub_device (DataFrame): logistic parameter
                topology (DataFrame): logistic parameter
                vessels (dict): logistic parameter

        self.__Simu_Param (dict): This parameter records the general
        information concerning the simulation
            keys:
                Nbodies (int) [-]:
                    Number of devices
                annual_Energy_Production_perD (numpy.ndarray) [Wh]:
                    Annual energy production of each device on the array.
                    The dimension of the array is Nbodies x 1 (WP2)
                arrayInfoLogistic (DataFrame) [-]:
                    Information about component_id, depth, x_coord, y_coord,
                    zone, bathymetry, soil type
                missionTime (float) [year]:
                    Simulation time
                power_prod_perD (numpy.ndarray) [W]:
                    Mean power production per device. The dimension of the
                    array is Nbodies x 1 (WP2)
                startOperationDate (datetime) [-]:
                    Date of simulation start


        self.__Control_Param (dict): This parameter records the O&M module
        control from GUI (to be extended in future)
            keys:
                whichOptim (list) [bool]:
                    Which O&M should be optimised [Unplanned corrective
                    maintenance, Condition based maintenance, Calendar
                    based maintenance]
                checkNoSolution (bool) [-]:
                    see below
                checkNoSolutionWP6Files (bool) [-]:
                    see below
                integrateSelectPort (bool) [-]:
                    see below)

                ###############################################################
                ###############################################################
                ###############################################################
                Some of the function developed by logistic takes some times
                for running. With the following flags is possible to control
                the call of such functions.

                Control_Param['integrateSelectPort'] is True  ->
                    callOM_PortSelection
                Control_Param['integrateSelectPort'] is False ->
                    do not call OM_PortSelection, set constant values for
                    port parameters

                # Control_Param['checkNoSolution'] is True  ->
                    check the feasibility of logistic solution before the
                    simulation
                # Control_Param['checkNoSolution'] is False ->
                    do not check the feasibility of logistic solution before
                    the simulation

                # dtocean_maintenance print flag
                # Control_Param['dtocean_maintenance_PRINT_FLAG'] is True  ->
                    print is allowed inside of dtocean_maintenance
                # Control_Param['dtocean_maintenance_PRINT_FLAG'] is False ->
                    print is not allowed inside of dtocean_maintenance

                # dtocean-logistics print flag
                # Control_Param['dtocean-logistics_PRINT_FLAG'] is True  ->
                    print is allowed inside of dtocean-logistics
                # Control_Param['dtocean-logistics_PRINT_FLAG'] is False ->
                    print is not allowed inside of dtocean-logistics

                # dtocean_maintenance test flag
                # Control_Param['dtocean_maintenance_TEST_FLAG'] is True  ->
                    print the results in excel files
                # Control_Param['dtocean_maintenance_TEST_FLAG'] is False ->
                    do not print the results in excel files

                ###############################################################
                ###############################################################
                ###############################################################


        self.__strFormat1 (str) [-]: converting between datetime and string
        self.__strFormat2 (str) [-]: converting between datetime and string
        self.__dayHours (float) [-]: Hours in one day
        self.__yearDays (float) [-]: Days in one year
        self.__delayEventsAfterCaBaMaHour (float) [hour]:
            Delay repair action after CaBaMa
        self.__energy_selling_price (float) [Euro/kWh]: Energy selling price
        arrayDict (dict) [-]:
            dictionary for the saving of model calculation
        startOperationDate (datetime) [-]: date of simulation start
        self.__powerOfDevices (list of float) [W]: power of devices
        self.__annual_Energy_Production_perD (list of float) [Wh]:
            Annual energy production per device
        self.__NrOfDevices (int) [-]: Number of devices
        self.__NrOfTurnOutDevices (int) [-]: Number of turn out devices
        self.__operationTimeYear (float) [year]:
            Operation time in years (mission time)
        self.__operationTimeDay (float) [day]: Operation time in days
        self.__endOperationDate (datetime) [day]: end date of array operation
        self.__UnCoMa_eventsTableKeys (list of str) [-]:
            keys of eventsTable (UnCoMa)
        self.__UnCoMa_outputEventsTableKeys (list of str) [-]:
            keys of outputEventsTable (UnCoMa)
        self.__NoPoisson_eventsTableKeys (list of str) [-]:
            Keys of eventsTableNoPoisson
        self.__UnCoMa_eventsTable (DataFrame) [-]: eventsTable (UnCoMa)
        self.__UnCoMa_outputEventsTable (DataFrame) [-]:
            eventsTable for output (UnCoMa)
        self.__eventsTableNoPoisson (DataFrame) [-]: eventsTable (NoPoisson)
        self.__summerTime (bool) [-]: summer time
        self.__winterTime (bool) [-]: winter time
        self.__totalWeekEndWorkingHour (float) [hour]:
            total weekend working hour
        self.__totalNotWeekEndWorkingHour (float) [hour]:
            total not weekend working hour
        self.__totalDayWorkingHour (float) [hour]: total day working hour
        self.__totalNightWorkingHour (float) [hour]: total night working hour
        self.__startDayWorkingHour (float) [-]: start hour of working
        self.__totalActionDelayHour (float) [hour]: total repair action delay
        self.__actActionDelayHour (float) [hour]: actual action delay
        self.__outputsOfWP6 (dict) [-]: output of WP6
        self.__om_logistic (dict) [-]: output of logistic
        self.__OUTPUT_dict_logistic (dict) [-]: output of logistic
        self.__logPhase_om (class) [-]: logistic parameter
        self.__vessels (dict) [-]: logistic parameter
        self.__equipments (dict) [-]: logistic parameter
        self.__ports (DataFrame) [-]: logistic parameter
        self.__portDistIndex (dict) [-]: logistic parameter
        self.__phase_order (DataFrame) [-]: logistic parameter
        self.__site (DataFrame) [-]: logistic parameter
        self.__metocean (DataFrame) [-]: logistic parameter
        self.__device (DataFrame) [-]: logistic parameter
        self.__sub_device (DataFrame) [-]: logistic parameter
        self.__landfall (DataFrame) [-]: logistic parameter
        self.__entry_point (DataFrame) [-]: logistic parameter
        self.__layout (DataFrame) [-]: logistic parameter
        self.__connerctors (DataFrame) [-]: logistic parameter
        self.__dynamic_cable (DataFrame) [-]: logistic parameter
        self.__static_cable (DataFrame) [-]: logistic parameter
        self.__cable_route (DataFrame) [-]: logistic parameter
        self.__connerctors (DataFrame) [-]: logistic parameter
        self.__external_protection (DataFrame) [-]: logistic parameter
        self.__topology (DataFrame) [-]: logistic parameter
        self.__schedule_OLC (DataFrame) [-]: logistic parameter
        self.__other_rates (DataFrame) [-]: logistic parameter
        self.__logisticKeys (DataFrame) [-]:
            keys of dataframe for logistic functions
        self.__wp6_outputsForLogistic (DataFrame) [-]:
            input for logistic module
        self.__ramPTR (class) [-]: pointer of RAM
        self.__eleclayout (str) [-]: Electrical layout architecture
        self.__systype (str) [-]: Type of system
        self.__elechierdict (str) [-]: RAM parameter
        self.__elecbomeg (str) [-]: RAM parameter
        self.__moorhiereg (str) [-]: RAM parameter
        self.__moorbomeg (str) [-]: RAM parameter
        self.__userhiereg (str) [-]: RAM parameter
        self.__userbomeg (str) [-]: RAM parameter
        self.__db (str) [-]: RAM parameter
        self.__rsubsysvalues (nested list) [-]: rsubsysvalues from RAM
        self.__rcompvalues (nested list) [-]: rcompvalues from RAM
        self.__arrayPTR (class) [-]: pointer of arrayClass
        self.__totalSeaTimeHour (float) [hour]: Total sea time
        self.__totalSeaTimeHour (float) [hour]: Total sea time
        self.__departOpDate (datetime) [-]: date of depart
        self.__endOpDate (datetime) [-]: date of end of operation
        self.__repairActionDate (datetime) [-]: date of repair action
        self.__errorFlag (bool) [-]: error flag
        self.__errorTable (DataFrame) [-]: error table
        self.__CaBaMa_nrOfMaxActions (int) [-]:
            maximum number of parallel actions in calendar based maintenance
        self.__CaBaMa_eventsTableKeys (list of str) [-]:
            keys of table CaBaMa_eventsTableKeys
        self.__CaBaMa_eventsTable (DataFrame) [-]: table CaBaMa_eventsTable
        self.__CaBaMa_outputEventsTableKeys (list of str) [-]:
            keys of table CaBaMa_eventsTableKeys
        self.__CaBaMa_outputEventsTable (DataFrame) [-]:
            table CaBaMa_eventsTable
        self.__CoBaMa_nrOfMaxActions (int) [-]:
            maximum number of parallel actions in condition based maintenance
        self.__CoBaMa_eventsTableKeys (list of str) [-]:
            keys of table CoBaMa_eventsTableKeys
        self.__CoBaMa_outputEventsTableKeys (list of str) [-]:
            keys of table CaBaMa_eventsTableKeys
        self.__CoBaMa_outputEventsTable (DataFrame) [-]:
            table CoBaMa_eventsTable
        self.__CoBaMa_eventsTable (DataFrame) [-]: table CoBaMa_eventsTable
        self.__actIdxOfUnCoMa (int) [-]: actual index of UnCoMa_eventsTable
        self.__flagCalcUnCoMa (bool) [-]: flag of UnCoMa_eventsTable
        self.__PrepTimeCalcUnCoMa (float) [hour]: preparation time
        self.__actIdxOfCaBaMa (int) [-]: actual index of CaBaMa_eventsTable
        self.__flagCalcCaBaMa (bool) [-]: flag of CaBaMa_eventsTable
        self.__PrepTimeCalcCaBaMa (float) [hour]: preparation time
        self.__failureRateFactorCoBaMa (float) [%]:
            factor for the correction of failure rate in case of condition
            based maintenance in %
        self.__actIdxOfCoBaMa (int) [-]: actual index of CoBaMa_eventsTable
        self.__flagCalcCoBaMa (bool) [-]: flag of CoBaMa_eventsTable
        self.__PrepTimeCalcCoBaMa (float) [hour]: preparation time
        self.__powerDeratingCoBaMa (float) [%]:
            power derating in case of condition based maintenance after the
            detction of soh_threshold
        self.__timeExtensionDeratingCoBaMaHour (float) [hours]:
            time extension in case of condition based maintenance after the
            detction of soh_threshold
        self.__checkNoSolution (bool) [-]: see below
        self.__integrateSelectPort (bool) [-]: see below
        self.__dtocean_maintenance_PRINT_FLAG (bool) [-]: see below
        self.__dtocean-logistics_PRINT_FLAG (bool) [-]: see below

        #######################################################################
        #######################################################################
        #######################################################################
        Some of the function developed by logistic takes some times for
        running. With the following flags is possible to control the call of
        such functions.

        self.__integrateSelectPort is True  ->
            call OM_PortSelection
        self.__integrateSelectPort is False ->
            do not call OM_PortSelection, set constant values for port
            parameters

        self.__checkNoSolution is True  ->
            check the feasibility of logistic solution before the simulation
        self.__checkNoSolution is False ->
        do not check the feasibility of logistic solution before the simulation

        self.__dtocean_maintenance_PRINT_FLAG is True  ->
            print is allowed inside of dtocean_maintenance
        self.__dtocean_maintenance_PRINT_FLAG is False ->
            print is not allowed inside of dtocean_maintenance

        self.__dtocean-logistics_PRINT_FLAG is True  ->
            print is allowed inside of dtocean-logistics
        self.__dtocean-logistics_PRINT_FLAG is False ->
            print is not allowed inside of dtocean-logistics

        self.__dtocean_maintenance_TEST_FLAG is True  ->
            print the results in excel files
        self.__dtocean_maintenance_TEST_FLAG is False ->
            do not print the results in excel files

        self.__readFailureRateFromRAM is True  ->
            Failure rate is read from RAM
        self.__readFailureRateFromRAM is False ->
            Failure rate is read from component table (IWES)

        self.__ignoreWeatherWindow is True  ->
            The case "NoWeatherWindowFound" will be ignored
        self.__ignoreWeatherWindow is False ->
            The case "NoWeatherWindowFound" wont be ignored

       ########################################################################
       ########################################################################
       ########################################################################

    '''

    def __init__(self, inputOMPTR):

        '''__init__ function: Saves the arguments in internal variabels.

        Args:
            inputOMPTR (class): pointer of inputOM class


        Returns:
            no returns

        '''

        #######################################################################

        # start: Read from inputOM
        # Save the instance pointer of inputOM
        self.__inputOMPTR = inputOMPTR

        # Read the inputs from core
        self.__Farm_OM          = self.__inputOMPTR.get_Farm_OM()
        self.__Component        = self.__inputOMPTR.get_Component()
        self.__Failure_Mode     = self.__inputOMPTR.get_Failure_Mode()
        self.__Repair_Action    = self.__inputOMPTR.get_Repair_Action()
        self.__Inspection       = self.__inputOMPTR.get_Inspection()
        self.__RAM_Param        = self.__inputOMPTR.get_RAM_Param()
        self.__Logistic_Param   = self.__inputOMPTR.get_Logistic_Param()
        self.__Simu_Param       = self.__inputOMPTR.get_Simu_Param()
        self.__Control_Param    = self.__inputOMPTR.get_Control_Param()

        self.__changeOfLabels()
        # end: Read from inputOM
        #######################################################################

        #######################################################################
        # start: Declaration of constants for mainCalc

        # For converting between datetime and string
        self.__strFormat1 = "%d:%m:%Y %H:%M:%S"
        self.__strFormat2 = "%Y-%m-%d %H:%M:%S"

        # Hours in one day
        self.__dayHours = 24.0

        # Days in one year
        self.__yearDays = 365.25

        # Delete repair action after CaBaMa [hour]
        self.__delayEventsAfterCaBaMaHour = 6*30*24

        # end: Declaration of constants for mainCalc
        #######################################################################

        #######################################################################
        # start: Declaration of general variables for mainCalc

        # Energy selling price [Euro/kWh]
        self.__energy_selling_price = self.__Farm_OM['energy_selling_price']

        # Instance pointer of arrayClass
        # Dictionary for saving the parameters
        self.__arrayDict = {}

        # Which O&M should be calculated?
        # [unplaned corrective maintenance, condition based maintenance,
        #  calandar based maintenance]
        self.__whichOptim = self.__Control_Param['whichOptim']

        # Start of operation date
        self.__startOperationDate = self.__Simu_Param['startOperationDate']

        # Power of devices [W]
        self.__powerOfDevices = self.__Simu_Param['power_prod_perD']

        # Annual_Energy_Production_perD [Wh]
        self.__annual_Energy_Production_perD = \
            self.__Simu_Param['annual_Energy_Production_perD']

        # Nr of devices []
        self.__NrOfDevices = self.__Simu_Param['Nbodies']

        # Nr of turn out devices []
        self.__NrOfTurnOutDevices = 0

        # Operation time in years (mission time)
        self.__operationTimeYear = float(self.__Simu_Param['missionTime'])

        # Operation time in days
        self.__operationTimeDay = self.__Simu_Param['missionTime'] * \
                                                                self.__yearDays

        # End of array operation
        self.__endOperationDate = self.__startOperationDate + \
                                    timedelta(days=self.__operationTimeDay)

        # Keys of eventsTable
        self.__UnCoMa_eventsTableKeys = ['failureRate',
                                         'repairActionEvents',
                                         'failureEvents',
                                         'belongsTo',
                                         'ComponentType',
                                         'ComponentSubType',
                                         'ComponentID',
                                         'FM_ID',
                                         'indexFM',
                                         'RA_ID']

        # eventsTable
        self.__UnCoMa_eventsTable = None

        # event table for output
        self.__UnCoMa_outputEventsTableKeys = ['failureRate [1/year]',
                                               'failureDate [-]',
                                               'repairActionRequestDate [-]',
                                               'repairActionDate [-]',
                                               'downtimeDuration [Hour]',
                                               'seeTimeDuration [Hour]',
                                               'waitingTimeDuration [Hour]',
                                               'downtimeDeviceList [-]',
                                               'ComponentType [-]',
                                               'ComponentSubType [-]',
                                               'ComponentID [-]',
                                               'FM_ID [-]',
                                               'RA_ID [-]',
                                               'indexFM [-]',
                                               'costLogistic [Euro]',
                                               'costOM_Labor [Euro]',
                                               'costOM_Spare [Euro]',
                                               'typeOfvessels [-]',
                                               'nrOfvessels [-]']


        self.__UnCoMa_outputEventsTable = pd.DataFrame(
                                index=[0],
                                columns=self.__UnCoMa_outputEventsTableKeys)

        # Keys of eventsTableNoPoisson
        self.__NoPoisson_eventsTableKeys  = ['repairActionEvents',
                                             'failureEvents',
                                             'belongsTo',
                                             'ComponentType',
                                             'ComponentSubType',
                                             'ComponentID',
                                             'FM_ID',
                                             'indexFM',
                                             'RA_ID',
                                             'failureRate',
                                             'Alarm']

        # eventsTableNoPoisson
        self.__eventsTableNoPoisson = None

        # summer time
        self.__summerTime = None

        # winter time
        self.__winterTime = None

        # total weekend working hour
        self.__totalWeekEndWorkingHour = None

        # total not weekend working hour
        self.__totalNotWeekEndWorkingHour = None

        # total day working hour
        self.__totalDayWorkingHour = None

        # total night working hour
        self.__totalNightWorkingHour = None

        # startDayWorkingHour
        self.__startDayWorkingHour = 6

        # total action delay
        self.__totalActionDelayHour = 0

        # actual action delay
        self.__actActionDelayHour = 0

        # end: Declaration of general variables for mainCalc
        #######################################################################



        #######################################################################
        # start: Declaration of outputs of WP6
        self.__outputsOfWP6 = {}
        self.__outputsOfWP6['env_assess [-]'] = {}
        self.__outputsOfWP6['env_assess [-]']['UnCoMa_eventsTable'] = {}
        self.__outputsOfWP6['env_assess [-]']['CaBaMa_eventsTable'] = {}
        self.__outputsOfWP6['env_assess [-]']['CoBaMa_eventsTable'] = {}

        self.__UnCoMa_dictEnvAssess = {}
        self.__CaBaMa_dictEnvAssess = {}
        self.__CoBaMa_dictEnvAssess = {}

        # for maintenance plans in WP6
        self.__outputsOfWP6['eventTables [-]'] = {}

        # LCOE of array (float) [Euro/KWh]
        self.__outputsOfWP6['lcoeOfArray [Euro/KWh]'] = 0

        # Annual energy of each devices (list of float) [Wh]
        self.__outputsOfWP6['annualEnergyOfDevices [Wh]'] = []

        # Annual down time of each devices (list of float) [h]
        self.__outputsOfWP6['annualDownTimeOfDevices [h]'] = []

        # Annual energy of array (float) [Wh]
        self.__outputsOfWP6['annualEnergyOfArray [Wh]'] = 0


        # CAPEX of array in case of condition based maintenance strategy
        # (float) [Euro]
        self.__outputsOfWP6['CapexOfArray [Euro]'] = 0

        # determine the CAPEX of the array
        if self.__Farm_OM['condition_based_maintenance'] == True:

            for iCnt in range(0,self.__Failure_Mode.shape[1]):

                column = self.__Failure_Mode.columns.values[iCnt]
                capex_condition = self.__Failure_Mode[column][
                                        'CAPEX_condition_based_maintenance']

                if not math.isnan(capex_condition) and capex_condition > 0:

                    self.__outputsOfWP6['CapexOfArray [Euro]'] = \
                        self.__outputsOfWP6['CapexOfArray [Euro]'] + \
                            capex_condition

        # Annual OPEX of array (float) [Euro]
        self.__outputsOfWP6['annualOpexOfArray [Euro]'] = 0

        # Information about error (-) [-]
        self.__outputsOfWP6['error [-]'] = None

        for iCnt in range(0,self.__NrOfDevices):
            self.__outputsOfWP6['annualEnergyOfDevices [Wh]'].append(0.0)
            self.__outputsOfWP6['annualDownTimeOfDevices [h]'].append(0.0)

        # end: Declaration of outputs of WP6
        #######################################################################


        #######################################################################
        # start: Declaration of variables for logistic

        # Declaration of output of logistic (dict)
        self.__om_logistic = {}

        # Declaration of output of logistic (dict)
        self.__OUTPUT_dict_logistic = {}

        # Declaration of variable for logistic (class)
        self.__logPhase_om = None

         # Declaration of variable for logistic (?)
        self.__vessels = self.__Logistic_Param['vessels']

        # Declaration of variable for logistic (?)
        self.__equipments = self.__Logistic_Param['equipments']

        # Declaration of variable for logistic (dataframe)
        self.__ports = self.__Logistic_Param['ports']

        # 'Dist_port [km]', 'Port_Index [-]'
        # Information about ports
        self.__portDistIndex = {}
        self.__portDistIndex['inspection'] = []
        self.__portDistIndex['repair']     = []

        # Default values for port
        self.__dummyDist_port   = 0.1#190
        self.__dummyPort_Index  = 21

        self.__portDistIndex['inspection'].append(self.__dummyDist_port)
        self.__portDistIndex['inspection'].append(self.__dummyPort_Index)

        self.__portDistIndex['repair'].append(self.__dummyDist_port)
        self.__portDistIndex['repair'].append(self.__dummyPort_Index)

        # Declaration of variable for logistic (dict)

        self.__phase_order = self.__Logistic_Param['phase_order']
        self.__site = self.__Logistic_Param['site']
        self.__metocean = self.__Logistic_Param['metocean']
        self.__device = self.__Logistic_Param['device']
        self.__sub_device = self.__Logistic_Param['sub_device']
        self.__landfall = self.__Logistic_Param['landfall']
        self.__entry_point = self.__Logistic_Param['entry_point']

        # Declaration of variable for logistic (?)
        self.__layout = self.__Logistic_Param['layout']

        self.__collection_point = self.__Logistic_Param['collection_point']
        self.__dynamic_cable = self.__Logistic_Param['dynamic_cable']
        self.__static_cable = self.__Logistic_Param['static_cable']
        self.__cable_route = self.__Logistic_Param['cable_route']
        self.__connectors = self.__Logistic_Param['connectors']
        self.__external_protection = self.__Logistic_Param[
                                                        'external_protection']
        self.__topology = self.__Logistic_Param['topology']
        self.__port_sf = self.__Logistic_Param['port_sf']
        self.__vessel_sf = self.__Logistic_Param['vessel_sf']
        self.__eq_sf = self.__Logistic_Param['eq_sf']
        self.__schedule_OLC = self.__Logistic_Param['schedule_OLC']
        self.__other_rates = self.__Logistic_Param['other_rates']

        # Initialise logistic operations and logistic phase

        # keys of dataframe for logistic functions
        self.__logisticKeys = ['ID [-]',
                               'element_type [-]',
                               'element_subtype [-]',
                               'element_ID [-]',
                               'depth [m]',
                               'x coord [m]',
                               'y coord [m]',
                               'zone [-]',
                               't_start [-]',
                               'd_acc [hour]',
                               'd_om [hour]',
                               'helideck [-]',
                               'Hs_acc [m]',
                               'Tp_acc [s]',
                               'Ws_acc [m/s]',
                               'Cs_acc [m/s]',
                               'Hs_om [m]',
                               'Tp_om [s]',
                               'Ws_om [m/s]',
                               'Cs_om [m/s]',
                               'technician [-]',
                               'sp_dry_mass [kg]',
                               'sp_length [m]',
                               'sp_width [m]',
                               'sp_height [m]',
                               'Dist_port [km]',
                               'Port_Index [-]',
                               'Bathymetry [m]',
                               'Soil type [-]',
                               'Prep_time [h]'
                               ]

        self.__wp6_outputsForLogistic = pd.DataFrame(
                                                index=[0],
                                                columns=self.__logisticKeys)

        # end: Declaration of variables for logistic
        #######################################################################

        #######################################################################
        # start: Declaration of variables for RAM

        # This variable will be used for saving of RAM instance.
        self.__ramPTR = None

        # Eleclayout -> radial, singlesidedstring, doublesidedstring,
        # multiplehubs
        self.__eleclayout = self.__RAM_Param['eleclayout']

        # systype -> 'tidefloat', 'tidefixed', 'wavefloat', 'wavefixed'
        self.__systype = self.__RAM_Param['systype']

        # elechierdict
        self.__elechierdict = self.__RAM_Param['elechierdict']

        # elecbomeg
        self.__elecbomeg = self.__RAM_Param['elecbomeg']

        # moorhiereg
        self.__moorhiereg = self.__RAM_Param['moorhiereg']

        # moorbomeg
        self.__moorbomeg = self.__RAM_Param['moorbomeg']

        # userhiereg
        self.__userhiereg = self.__RAM_Param['userhiereg']

        # userbomeg
        self.__userbomeg = self.__RAM_Param['userbomeg']

        # db
        self.__db = self.__RAM_Param['db']


        # Declaration of output of RAM
        #self.__ram = {}

        # list rsubsysvalues from RAM
        self.__rsubsysvalues = []

        # list rcompvalues from RAM
        self.__rcompvalues = []


        # end: Declaration of variables for RAM
        #######################################################################


        #######################################################################
        # start: Declaration of variables for arrayClass

        # Instance pointer of arrayClass
        self.__arrayPTR = None

        # end: Declaration of variables for arrayClass
        #######################################################################


        #######################################################################
        # start: Declaration of internally parameters for mainCalc

        # Total sea time [hour]
        self.__totalSeaTimeHour = 0

        # date of depart [datetime]
        self.__departOpDate = None

        # date of end of operation [datetime]
        self.__endOpDate = None

        # date of repair action [datetime]
        self.__repairActionDate = None

        # error flag [-]
        self.__errorFlag = False

        # error table [-]
        errorKeys  = ['error_ID [-]',
                      'element_ID [-]',
                      'element_type [-]',
                      'element_subtype [-]',
                      'FM_ID [-]',
                      'RA_ID [-]',
                      'deck area [m^2]',
                      'deck cargo [t]',
                      'deck loading [t/m^2]',
                      'sp_dry_mass [kg]',
                      'sp_length [m]',
                      'sp_width [m]',
                      'sp_height [m]']

        self.__errorTable = pd.DataFrame(index=[0],columns= errorKeys)

        # end: Declaration of internally parameters for mainCalc
        #######################################################################


        #######################################################################
        # start: Parameter of Condition based maintenance and Calendar based
        # maintenance

        # Calendar based maintenance: Number of parallel actions [-]
        self.__CaBaMa_nrOfMaxActions = 10

        # Keys of CaBaMa_eventsTableKeys
        self.__CaBaMa_eventsTableKeys  = ['startActionDate',
                                          'endActionDate',
                                          'currentStartActionDate',
                                          'currentEndActionDate',
                                          'belongsTo',
                                          'belongsToSort',
                                          'ComponentType',
                                          'ComponentSubType',
                                          'ComponentID',
                                          'FM_ID',
                                          'indexFM',
                                          'RA_ID',
                                          'logisticCost',
                                          'omCost']

        # CaBaMa_eventsTableKeys
        self.__CaBaMa_eventsTable = pd.DataFrame(
                                        index=[0],
                                        columns=self.__CaBaMa_eventsTableKeys)

        # CaBaMa_eventsTableKeys
        self.__CaBaMa_outputEventsTableKeys = ['repairActionRequestDate [-]',
                                               'repairActionDate [-]',
                                               'downtimeDuration [Hour]',
                                                'downtimeDeviceList [-]',
                                                'ComponentType [-]',
                                                'ComponentSubType [-]',
                                                'ComponentID [-]',
                                                'FM_ID [-]',
                                                'RA_ID [-]',
                                                'indexFM [-]',
                                                'costLogistic [Euro]',
                                                'costOM_Labor [Euro]',
                                                'costOM_Spare [Euro]']

        self.__CaBaMa_outputEventsTable = pd.DataFrame(
                                index=[0],
                                columns=self.__CaBaMa_outputEventsTableKeys)

        # Condition based maintenance: Number of parallel actions [-]
        self.__CoBaMa_nrOfMaxActions = 10

        # Keys of CoBaMa_eventsTableKeys
        self.__CoBaMa_eventsTableKeys  = ['startActionDate',
                                          'endActionDate',
                                          'currentStartDate',
                                          'currentEndDate',
                                          'currentAlarmDate',
                                          'belongsTo',
                                          'ComponentType',
                                          'ComponentSubType',
                                          'ComponentID',
                                          'FM_ID',
                                          'indexFM',
                                          'RA_ID',
                                          'threshold',
                                          'failureRate',
                                          'flagCaBaMa']

        # CoBaMa_eventsTableKeys
        self.__CoBaMa_eventsTable = pd.DataFrame(
                                        index=[0],
                                        columns=self.__CoBaMa_eventsTableKeys)

        # CaBaMa_eventsTableKeys
        self.__CoBaMa_outputEventsTableKeys = ['failureRate [1/year]',
                                               'currentAlarmDate [-]',
                                               'repairActionRequestDate [-]',
                                               'repairActionDate [-]',
                                               'downtimeDuration [Hour]',
                                               'downtimeDeviceList [-]',
                                               'ComponentType [-]',
                                               'ComponentSubType [-]',
                                               'ComponentID [-]',
                                               'FM_ID [-]',
                                               'RA_ID [-]',
                                               'indexFM [-]',
                                               'costLogistic [Euro]',
                                               'costOM_Labor [Euro]',
                                               'costOM_Spare [Euro]']

        self.__CoBaMa_outputEventsTable = pd.DataFrame(
                                index=[0],
                                columns=self.__CoBaMa_outputEventsTableKeys)

        # actual index of UnCoMa_eventsTable
        self.__actIdxOfUnCoMa = 0
        self.__flagCalcUnCoMa = False
        self.__PrepTimeCalcUnCoMa = 48

        # actual index of CaBaMa_eventsTable
        self.__actIdxOfCaBaMa = 0
        self.__flagCalcCaBaMa = False
        self.__PrepTimeCalcCaBaMa = 0

        # actual index of CoBaMa_eventsTable
        self.__failureRateFactorCoBaMa = 0
        self.__actIdxOfCoBaMa = 0
        self.__flagCalcCoBaMa = False
        self.__PrepTimeCalcCoBaMa = 0
        # in %
        self.__powerDeratingCoBaMa = 50
        # [hours]
        self.__timeExtensionDeratingCoBaMaHour = 3 *30 * self.__dayHours

        # end: Declaration of internally parameters for mainCalc
        #######################################################################


        #######################################################################
        # Start: Flags for dtocean_maintenance test purposes

        self.__integrateSelectPort = self.__Control_Param[
                                            'integrateSelectPort']
        self.__checkNoSolution = self.__Control_Param['checkNoSolution']
        self.__dtocean_maintenance_PRINT_FLAG = self.__Control_Param[
                                            'dtocean_maintenance_PRINT_FLAG']
        self.__dtocean_logistics_PRINT_FLAG = self.__Control_Param[
                                            'dtocean_logistics_PRINT_FLAG']
        self.__dtocean_maintenance_TEST_FLAG = self.__Control_Param[
                                            'dtocean_maintenance_TEST_FLAG']
        self.__readFailureRateFromRAM = self.__Control_Param[
                                            'readFailureRateFromRAM']
        self.__ignoreWeatherWindow = self.__Control_Param[
                                            'ignoreWeatherWindow']

        return

    def __changeOfLabels(self):

        '''__changeOfLabels function: changes the labels of some tables

        '''

        # Component -> Component_ID
        # Component
        col_map = dict(zip(self.__Component.columns,
                           list(self.__Component.loc['Component_ID'])))

        self.__Component.rename(columns=col_map, inplace=True)

        # Component -> Component_ID
        # Simu_Param
        components = self.__Simu_Param['arrayInfoLogistic'].loc['Component_ID']
        col_map = dict(zip(self.__Simu_Param['arrayInfoLogistic'].columns,
                           list(components)))

        self.__Simu_Param['arrayInfoLogistic'].rename(columns=col_map,
                                                      inplace=True)

        # Repair_Action
        nuOfColumnsRA = self.__Repair_Action.shape[1]
        idListRA = list(self.__Repair_Action.loc['Component_ID'])
        fmListRA = list(self.__Repair_Action.loc['FM_ID'])

        newColumnsRA = []
        for iCnt in range(0,nuOfColumnsRA):
            newColumnsRA.append('dummy')

        # Inspection
        nuOfColumnsInsp = self.__Inspection.shape[1]
        idListInsp = list(self.__Inspection.loc['Component_ID'])
        fmListInsp = list(self.__Inspection.loc['FM_ID'])
        newColumnsInsp = []
        for iCnt in range(0,nuOfColumnsInsp):
            newColumnsInsp.append('dummy')

        # Failure_Mode
        nuOfColumns = self.__Failure_Mode.shape[1]
        idList = list(self.__Failure_Mode.loc['Component_ID'])
        fmList = list(self.__Failure_Mode.loc['FM_ID'])

        newColumns = []
        for iCnt in range(0,nuOfColumns):
            if len(newColumns) == 0:
                newColumns.append(idList[iCnt] + '_1')

            else:
                index = 0
                for iCnt1 in range(0,len(newColumns)):
                    if idList[iCnt] == string.rsplit(newColumns[iCnt1],'_')[0]:
                         index = index + 1

                if index == 0:
                    newColumns.append(idList[iCnt] + '_1')
                else:
                    newColumns.append(idList[iCnt] + '_' + str(index + 1))

            indexList = -1

            for iCnt1 in range(0, nuOfColumnsRA):

                if (idListRA[iCnt1] == idList[iCnt] and
                    fmListRA[iCnt1] == fmList[iCnt]):

                    indexList = iCnt1
                    break

            if indexList != -1:
                newColumnsRA[indexList] = newColumns[-1]

            indexList = -1

            for iCnt1 in range(0, nuOfColumnsInsp):

                if (idListInsp[iCnt1] == idList[iCnt] and
                    fmListInsp[iCnt1] == fmList[iCnt]):

                    indexList = iCnt1
                    break

            if indexList != -1:
                newColumnsInsp[indexList] = newColumns[-1]

        # Failure_Mode
        col_map = dict(zip(self.__Failure_Mode.columns, newColumns))
        self.__Failure_Mode.rename(columns=col_map, inplace=True)

        # Repair_Action
        col_map = dict(zip(self.__Repair_Action.columns, newColumnsRA))
        self.__Repair_Action.rename(columns=col_map, inplace=True)

        # Inspection
        col_map = dict(zip(self.__Inspection.columns, newColumnsInsp))
        self.__Inspection.rename(columns=col_map, inplace=True)

        return

    def __call__(self):

        '''__call__ function: call function

        '''

        # Execution of functions for the calculation of LCOE
        self.executeCalc()

        return

    def executeCalc(self):

        '''executeCalc function: Execution of functions for the calculation of
        LCOE

        Returns:
            self.__outputsOfWP6 (dict): Output of WP6

        '''

        # Initialisation
        self.__initCalc()

        if (self.__integrateSelectPort == True or
            self.__checkNoSolution == True):

            self.__initCheck()

            if self.__errorFlag == True:

                # error handling
                self.__outputsOfWP6['error [-]'] = self.__errorTable

            else:

                ComponentType    = ''
                ComponentSubType = ''
                ComponentID      = ''
                RA_ID            = ''
                FM_ID            = ''
                deck_area        = ''
                deck_cargo       = ''
                deck_loading     = ''
                sp_dry_mass      = ''
                sp_length        = ''
                sp_width         = ''
                sp_height        = ''

                values = ['NoError',
                          ComponentID,
                          ComponentType,
                          ComponentSubType,
                          FM_ID,
                          RA_ID,
                          deck_area,
                          deck_cargo,
                          deck_loading,
                          sp_dry_mass,
                          sp_length,
                          sp_width,
                          sp_height]

                self.__errorTable.ix[0] = values

                # noError
                self.__outputsOfWP6['error [-]'] = self.__errorTable

            return self.__outputsOfWP6

        ComponentType    = ''
        ComponentSubType = ''
        ComponentID      = ''
        RA_ID            = ''
        FM_ID            = ''
        deck_area        = ''
        deck_cargo       = ''
        deck_loading     = ''
        sp_dry_mass      = ''
        sp_length        = ''
        sp_width         = ''
        sp_height        = ''

        values = ['NoError',
                  ComponentID,
                  ComponentType,
                  ComponentSubType,
                  FM_ID,
                  RA_ID,
                  deck_area,
                  deck_cargo,
                  deck_loading,
                  sp_dry_mass,
                  sp_length,
                  sp_width,
                  sp_height]

        self.__errorTable.ix[0] = values

        # noError
        self.__outputsOfWP6['error [-]'] = self.__errorTable

        # calc LCOE of array
        self.__calcLCOE_OfArray()

        return self.__outputsOfWP6

    def __initCalc(self):

        '''__initCalc function: some initialisation calculations

        '''

        # mission time in hours
        mission_time = self.__operationTimeYear * self.__yearDays * \
                                                            self.__dayHours

        # target mean time to failure in hours
        target_time = 0.4 * self.__operationTimeYear * self.__yearDays * \
                                                            self.__dayHours

        input_variables = Variables(mission_time,
                                    target_time,
                                    self.__systype,
                                    self.__db,
                                    self.__eleclayout,
                                    self.__elechierdict,
                                    self.__elecbomeg,
                                    self.__moorhiereg,
                                    self.__moorbomeg,
                                    self.__userhiereg,
                                    self.__userbomeg)

        # Make an instance of RAM
        self.__ramPTR = Main(input_variables)

        # calculation of RAM
        self.__ram = self.__calcRAM()

        # make instance of arrayClass
        self.__arrayPTR = Array(self.__startOperationDate,
                                self.__operationTimeDay,
                                self.__rcompvalues,
                                self.__rsubsysvalues,
                                self.__eleclayout,
                                self.__systype,
                                self.__UnCoMa_eventsTableKeys,
                                self.__NoPoisson_eventsTableKeys,
                                self.__dtocean_maintenance_PRINT_FLAG,
                                self.__readFailureRateFromRAM)

        # Read from RAM and calculate the poisson events of failure rates
        (self.__arrayDict,
         self.__UnCoMa_eventsTable,
         self.__eventsTableNoPoisson) = self.__arrayPTR.executeFEM(
                                         self.__arrayDict,
                                         self.__UnCoMa_eventsTable,
                                         self.__eventsTableNoPoisson,
                                         self.__Component,
                                         self.__Failure_Mode,
                                         self.__Repair_Action,
                                         self.__Inspection,
                                         self.__annual_Energy_Production_perD)

        if (self.__Farm_OM['calendar_based_maintenance'] == True or
            self.__Farm_OM['condition_based_maintenance'] == True):

            loopCalendar  = 0
            loopCondition = 0

            for iCnt in range(0, len(self.__eventsTableNoPoisson)):

                ComponentID = self.__eventsTableNoPoisson.ComponentID[iCnt]
                ComponentSubType = \
                    self.__eventsTableNoPoisson.ComponentSubType[iCnt]
                ComponentType = self.__eventsTableNoPoisson.ComponentType[iCnt]
                FM_ID = self.__eventsTableNoPoisson.FM_ID[iCnt]
                RA_ID = self.__eventsTableNoPoisson.RA_ID[iCnt]
                belongsTo = self.__eventsTableNoPoisson.belongsTo[iCnt]
                indexFM = self.__eventsTableNoPoisson.indexFM[iCnt]
                failureRate = self.__eventsTableNoPoisson.failureRate[iCnt]

                flagCaBaMa = False

                if self.__Farm_OM['calendar_based_maintenance'] == True:

                    if 'device' in belongsTo:
                        belongsToSort = 'device'
                    else:
                        belongsToSort = belongsTo

                    flagDummy = False
                    startActionDate = pd.to_datetime(self.__Component.at[
                                    'start_date_calendar_based_maintenance',
                                    ComponentID]).to_datetime()
                    endActionDate = pd.to_datetime(self.__Component.at[
                                    'end_date_calendar_based_maintenance',
                                    ComponentID]).to_datetime()
                    interval = self.__Component.at[
                                    'interval_calendar_based_maintenance',
                                    ComponentID]

                    if (type(startActionDate) != datetime.datetime or
                        type(endActionDate) != datetime.datetime or
                        math.isnan(interval) == True):
                        flagDummy = True

                    if flagDummy == False:

                        flagCaBaMa = True

                        if (self.__startOperationDate <= startActionDate and
                            startActionDate <= self.__endOperationDate):

                            startActionDateDummy = startActionDate
                            endActionDateDummy = endActionDate

                            while (startActionDateDummy <
                                               self.__endOperationDate):

                                values = [startActionDateDummy,
                                          endActionDateDummy,
                                          startActionDateDummy,
                                          endActionDateDummy,
                                          belongsTo,
                                          belongsToSort,
                                          ComponentType,
                                          ComponentSubType,
                                          ComponentID,
                                          FM_ID,
                                          indexFM,
                                          RA_ID,
                                          0,
                                          0]

                                self.__CaBaMa_eventsTable.ix[loopCalendar] = \
                                                                        values

                                loopCalendar = loopCalendar + 1
                                n_days = interval * self.__yearDays

                                startActionDateDummy = startActionDateDummy + \
                                    timedelta(days=n_days)
                                endActionDateDummy = endActionDateDummy + \
                                    timedelta(days=n_days)

                if self.__Farm_OM['condition_based_maintenance'] == True:

                    flagDummy = False
                    startActionDate = pd.to_datetime(self.__Component.at[
                            'start_date_calendar_based_maintenance',
                            ComponentID]).to_datetime()
                    endActionDate   = pd.to_datetime(self.__Component.at[
                            'end_date_calendar_based_maintenance',
                            ComponentID]).to_datetime()
                    threshold = self.__Component.at['soh_threshold',
                                                    ComponentID] / 100.0

                    if (type(startActionDate) != datetime.datetime or
                        type(endActionDate) != datetime.datetime or
                        threshold < 0 or
                        1 < threshold or
                        math.isnan(threshold) == True):

                        flagDummy = True

                    if flagDummy == False:

                        currentStartActionDate = self.__startOperationDate

                        failureRateDummy = failureRate - failureRate * \
                                    (self.__failureRateFactorCoBaMa / 100.0)

                        frate = failureRateDummy / self.__yearDays

                        poissonValue = poissonProcess(currentStartActionDate,
                                                      self.__operationTimeDay,
                                                      frate)

                        self.__arrayDict[ComponentID] \
                                        ['CoBaMa_FR List'] \
                                        [indexFM - 1] = failureRateDummy
                        self.__arrayDict[ComponentID] \
                                        ['CoBaMa_initOpEventsList'] \
                                        [indexFM - 1] = poissonValue

                        if 0 < len(poissonValue):

                            currentEndActionDate = poissonValue[0]

                            dur_secs = (currentEndActionDate -
                                            currentStartActionDate
                                                            ).total_seconds()
                            dummy = (dur_secs / 3600) * (1.0 - threshold)

                            alarmDate = self.__startOperationDate + \
                                                    timedelta(hours=dummy)

                            values = [startActionDate,
                                      endActionDate,
                                      currentStartActionDate,
                                      currentEndActionDate,
                                      alarmDate,
                                      belongsTo,
                                      ComponentType,
                                      ComponentSubType,
                                      ComponentID,
                                      FM_ID,
                                      indexFM,
                                      RA_ID,
                                      threshold,
                                      failureRateDummy,
                                      flagCaBaMa]
                            self.__CoBaMa_eventsTable.ix[loopCondition] = \
                                                                        values

                            loopCondition = loopCondition + 1

            # sort of calendar_based_maintenance
            if (self.__Farm_OM['calendar_based_maintenance'] == True and
                loopCalendar != 0):

                # 1: sort of CaBaMa_eventsTable
                self.__CaBaMa_eventsTable.sort(columns=['startActionDate',
                                                        'ComponentSubType',
                                                        'FM_ID'],
                                               inplace=True)

                # 2: sort of CaBaMa_eventsTable
                self.__CaBaMa_eventsTable.sort(columns=['startActionDate',
                                                        'belongsToSort'],
                                               inplace=True)

                # start index with 0
                self.__CaBaMa_eventsTable.reset_index(drop=True, inplace=True)

            # sort of condition_based_maintenance
            if (self.__Farm_OM['condition_based_maintenance'] == True and
                0 < len(self.__CoBaMa_eventsTable)):

                # sort of CoBaMa_eventsTable
                self.__CoBaMa_eventsTable.sort(columns=['currentAlarmDate'],
                                               inplace=True)

                # start index with 0
                self.__CoBaMa_eventsTable.reset_index(drop=True, inplace=True)


        if (self.__Farm_OM['corrective_maintenance'] == True and
            0 < len(self.__UnCoMa_eventsTable)):

            # remove the same entries from self.__UnCoMa_eventsTable in case
            # of condition_based_maintenance
            if (self.__Farm_OM['condition_based_maintenance'] == True and
                0 < len(self.__CoBaMa_eventsTable)):

                for iCnt in range(0, len(self.__CoBaMa_eventsTable)):

                    belongsTo = self.__CoBaMa_eventsTable.belongsTo[iCnt]
                    ComponentType = \
                        self.__CoBaMa_eventsTable.ComponentType[iCnt]
                    ComponentSubType = \
                        self.__CoBaMa_eventsTable.ComponentSubType[iCnt]
                    ComponentID = self.__CoBaMa_eventsTable.ComponentID[iCnt]
                    indexFM = self.__CoBaMa_eventsTable.indexFM[iCnt]
                    FM_ID = self.__CoBaMa_eventsTable.FM_ID[iCnt]
                    RA_ID = self.__CoBaMa_eventsTable.RA_ID[iCnt]

                    tempdf = self.__UnCoMa_eventsTable

                    tempdf = tempdf.loc[
                        (tempdf['belongsTo'] == belongsTo) & \
                        (tempdf['ComponentType'] == ComponentType) & \
                        (tempdf['ComponentSubType'] == ComponentSubType) & \
                        (tempdf['ComponentID'] == ComponentID) & \
                        (tempdf['indexFM'] == indexFM) & \
                        (tempdf['FM_ID'] == FM_ID) & \
                        (tempdf['RA_ID'] == RA_ID)]

                    self.__UnCoMa_eventsTable.drop(tempdf.index,
                                                   inplace=True)

                # start index with 0
                self.__UnCoMa_eventsTable.reset_index(drop=True,
                                                      inplace=True)

            # change of self.__UnCoMa_eventsTable concerning
            for iCnt in range(0, len(self.__UnCoMa_eventsTable)):

                # shift repairActionEvents
                failureEvents   = self.__UnCoMa_eventsTable.failureEvents[iCnt]
                ComponentID     = self.__UnCoMa_eventsTable.ComponentID[iCnt]
                FM_ID           = self.__UnCoMa_eventsTable.FM_ID[iCnt]
                indexFM         = self.__UnCoMa_eventsTable.indexFM[iCnt]
                CompIDWithIndex = ComponentID + '_' + str(indexFM)

                shiftHoursDummy1 = 0
                logic = 'Insp' in FM_ID

                if not logic:

                    # repairAction
                    shiftHoursDummy1 = self.__Repair_Action[
                                                CompIDWithIndex]['delay_spare']

                    delay_crew = self.__Repair_Action[
                                                CompIDWithIndex]['delay_crew']
                    delay_org = self.__Repair_Action[
                                        CompIDWithIndex]['delay_organisation']
                    shiftHoursDummy2 = delay_crew + delay_org

                else:

                    # inspection
                    shiftHoursDummy1 = 0

                    delay_crew = self.__Inspection[
                                                CompIDWithIndex]['delay_crew']
                    delay_org = self.__Inspection[
                                        CompIDWithIndex]['delay_organisation']
                    shiftHoursDummy2 = delay_crew + delay_org

                shiftHours = float(max(shiftHoursDummy1, shiftHoursDummy2))
                shiftDate = failureEvents + timedelta(hours=shiftHours)

                self.__UnCoMa_eventsTable.loc[iCnt,
                                              'repairActionEvents'] = shiftDate

            # sort of eventsTable
            self.__UnCoMa_eventsTable.sort(
                                    columns=self.__UnCoMa_eventsTableKeys[1],
                                    inplace=True)

            # start index with 0
            self.__UnCoMa_eventsTable.reset_index(drop=True, inplace=True)

        return

    def __calcRAM(self):

        '''__calcRAM function: calls of dtocean-reliability and saves the
        results

        '''

        # Execute call method of RAM
        self.__ramPTR()

        # list rsubsysvalues from RAM
        self.__rsubsysvalues = self.__ramPTR.rsubsysvalues3

        # list rcompvalues from RAM
        self.__rcompvalues = self.__ramPTR.rcompvalues3

        return

    # Selection of port for inspection and repair
    def __initCheck(self):

        '''__initCheck function: Selection of port for inspection and repair
        and check "NoSolutionsFound"

        '''

        dummyCheckNoSolution = True

        # should OM_PortSelection from logistic be called?
        if self.__integrateSelectPort == True:

            outputsForPortSelection = pd.DataFrame(index=[0],
                                                   columns=self.__logisticKeys)

            # find the maximum of 'sp_dry_mass [kg]', 'sp_length [m]',
            # 'sp_width [m]', 'sp_height [m]'
            sp_dry_mass_dummy       = 0
            #index_sp_dry_mass_dummy = 0

            sp_length_dummy         = 0
            #index_sp_length_dummy   = 0

            sp_width_dummy          = 0
            #index_sp_width_dummy    = 0

            sp_height_dummy         = 0
            #index_sp_height_dummy   = 0

            self.__portDistIndex['inspection'] = []
            self.__portDistIndex['repair']     = []

            for iCnt in range(0,len(self.__eventsTableNoPoisson)):

                # actualIndexOfRepairTable is determined
                # do the the reapir
                ComponentType = self.__eventsTableNoPoisson.ComponentType[iCnt]
                ComponentSubType = \
                    self.__eventsTableNoPoisson.ComponentSubType[iCnt]
                ComponentID = self.__eventsTableNoPoisson.ComponentID[iCnt]
                RA_ID = self.__eventsTableNoPoisson.RA_ID[iCnt]
                FM_ID = self.__eventsTableNoPoisson.FM_ID[iCnt]
                belongsTo = self.__eventsTableNoPoisson.belongsTo[iCnt]

                indexFM = self.__eventsTableNoPoisson.indexFM[iCnt]
                CompIDWithIndex = ComponentID + '_' + str(indexFM)

                # max of values
                sp_dry_mass = self.__Failure_Mode[CompIDWithIndex][
                                                                'spare_mass']

                if sp_dry_mass_dummy < sp_dry_mass:
                    sp_dry_mass_dummy = sp_dry_mass

                sp_length = self.__Failure_Mode[CompIDWithIndex][
                                                                'spare_length']

                if sp_length_dummy < sp_length:
                    sp_length_dummy = sp_length

                sp_width = self.__Failure_Mode[CompIDWithIndex]['spare_width']

                if sp_width_dummy < sp_width:
                    sp_width_dummy = sp_width

                sp_height = self.__Failure_Mode[CompIDWithIndex][
                                                                'spare_height']

                if sp_height_dummy < sp_height:
                    sp_height_dummy = sp_height

            # Inspection case
            # *****************************************************************
            # *****************************************************************
            # *****************************************************************
            values = ['INS_PORT',
                      '',
                      '',
                      '',
                      '',
                      self.__entry_point['x coord [m]'].ix[0],
                      self.__entry_point['y coord [m]'].ix[0],
                      self.__entry_point['zone [-]'].ix[0],
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      sp_dry_mass_dummy,
                      sp_length_dummy,
                      sp_width_dummy,
                      sp_height_dummy,
                      '',
                      '',
                      '',
                      '',
                      0]

            outputsForPortSelection.ix[0] = values

            om_port = select_port_OM.OM_port(outputsForPortSelection,
                                             self.__ports)

            # Check if there is a solution
            # Currently no possibility to check is implemented in logistic,
            # set it to False
            if False:

                self.__errorFlag = True

                ComponentType    = ''
                ComponentSubType = ''
                ComponentID      = ''
                RA_ID            = ''
                FM_ID            = ''
                deck_area        = ''
                deck_cargo       = ''
                deck_loading     = ''
                sp_dry_mass      = ''
                sp_length        = ''
                sp_width         = ''
                sp_height        = ''

                values = ['NoInspPortFound',
                          ComponentID,
                          ComponentType,
                          ComponentSubType,
                          FM_ID,
                          RA_ID,
                          deck_area,
                          deck_cargo,
                          deck_loading,
                          sp_dry_mass,
                          sp_length,
                          sp_width,
                          sp_height]

                self.__errorTable.ix[iCnt] = values
                dummyCheckNoSolution = False

            else:

                self.__portDistIndex['inspection'].append(
                        om_port['Distance port-site [km]'])
                self.__portDistIndex['inspection'].append(
                        om_port['Port database index [-]'])


            # Repair case
            # *****************************************************************
            # *****************************************************************
            # *****************************************************************
            values = ['OM_PORT',
                      '',
                      '',
                      '',
                      '',
                      self.__entry_point['x coord [m]'].ix[0],
                      self.__entry_point['y coord [m]'].ix[0],
                      self.__entry_point['zone [-]'].ix[0],
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      '',
                      sp_dry_mass_dummy,
                      sp_length_dummy,
                      sp_width_dummy,
                      sp_height_dummy,
                      '',
                      '',
                      '',
                      '',
                      0]


            outputsForPortSelection.ix[0] = values

            # Port Selection based on input

            om_port = select_port_OM.OM_port(outputsForPortSelection,
                                             self.__ports)

            # Check if there is a solution
            # Currently no possibility to check is implemented in logistic,
            # set it to False
            if False:

                self.__errorFlag = True

                ComponentType    = ''
                ComponentSubType = ''
                ComponentID      = ''
                RA_ID            = ''
                FM_ID            = ''
                deck_area        = ''
                deck_cargo       = ''
                deck_loading     = ''
                sp_dry_mass      = ''
                sp_length        = ''
                sp_width         = ''
                sp_height        = ''

                values = ['NoRepairPortFound',
                          ComponentID,
                          ComponentType,
                          ComponentSubType,
                          FM_ID,
                          RA_ID,
                          deck_area,
                          deck_cargo,
                          deck_loading,
                          sp_dry_mass,
                          sp_length,
                          sp_width,
                          sp_height]

                self.__errorTable.ix[iCnt] = values

                dummyCheckNoSolution = False

            else:
                self.__portDistIndex['repair'].append(
                        om_port['Distance port-site [km]'])
                self.__portDistIndex['repair'].append(
                        om_port['Port database index [-]'])

        if self.__checkNoSolution == True and dummyCheckNoSolution == True:

            indexNoSolutionsFound = []

            # NoSolutionsFound case
            # *****************************************************************
            # *****************************************************************
            # *****************************************************************
            loop = 0

            for iCnt in range(0, len(self.__eventsTableNoPoisson)):

                ComponentType = self.__eventsTableNoPoisson.ComponentType[iCnt]
                ComponentSubType = \
                    self.__eventsTableNoPoisson.ComponentSubType[iCnt]
                ComponentID = self.__eventsTableNoPoisson.ComponentID[iCnt]
                FM_ID = self.__eventsTableNoPoisson.FM_ID[iCnt]
                RA_ID = self.__eventsTableNoPoisson.RA_ID[iCnt]
                repairActionEvents = self.__startOperationDate
                belongsTo = self.__eventsTableNoPoisson.belongsTo[iCnt]
                repairActionDateStr = repairActionEvents.strftime(
                                                            self.__strFormat1)
                CompIDWithIndex = ComponentID + \
                        '_' + str(self.__eventsTableNoPoisson.indexFM[iCnt])

                # for logistic
                sp_dry_mass = self.__Failure_Mode[CompIDWithIndex][
                                                                'spare_mass']
                sp_length   = self.__Failure_Mode[CompIDWithIndex][
                                                                'spare_length']
                sp_width    = self.__Failure_Mode[CompIDWithIndex][
                                                                'spare_width']
                sp_height   = self.__Failure_Mode[CompIDWithIndex][
                                                                'spare_height']

                d_acc       = ''
                d_om        = ''
                helideck    = ''
                Hs_acc      = ''
                Tp_acc      = ''
                Ws_acc      = ''
                Cs_acc      = ''
                Hs_om       = ''
                Tp_om       = ''
                Ws_om       = ''
                Cs_om       = ''

                if 'Insp' in FM_ID:

                    # for logistic
                    technician = self.__Inspection[CompIDWithIndex][
                                                    'number_technicians'] + \
                                 self.__Inspection[CompIDWithIndex][
                                                    'number_specialists']
                    Dist_port = self.__portDistIndex['inspection'][0]
                    Port_Index = self.__portDistIndex['inspection'][1]

                else:

                    # for logistic
                    technician = self.__Repair_Action[CompIDWithIndex][
                                                    'number_technicians'] + \
                                 self.__Repair_Action[CompIDWithIndex][
                                                     'number_specialists']
                    Dist_port = self.__portDistIndex['repair'][0]
                    Port_Index = self.__portDistIndex['repair'][1]


                if belongsTo == 'Array':

                    depth = self.__Simu_Param['arrayInfoLogistic'][
                                                ComponentID]['depth']
                    x_coord = self.__Simu_Param['arrayInfoLogistic'][
                                                ComponentID]['x coord']
                    y_coord = self.__Simu_Param['arrayInfoLogistic'][
                                                ComponentID]['y coord']
                    zone = self.__Simu_Param['arrayInfoLogistic'][
                                                ComponentID]['zone']
                    Bathymetry = self.__Simu_Param['arrayInfoLogistic'][
                                                ComponentID]['Bathymetry']
                    Soil_type = self.__Simu_Param['arrayInfoLogistic'][
                                                ComponentID]['Soil type']

                else:

                    depth = self.__Simu_Param['arrayInfoLogistic'][
                                                belongsTo]['depth']
                    x_coord = self.__Simu_Param['arrayInfoLogistic'][
                                                belongsTo]['x coord']
                    y_coord = self.__Simu_Param['arrayInfoLogistic'][
                                                belongsTo]['y coord']
                    zone = self.__Simu_Param['arrayInfoLogistic'][
                                                belongsTo]['zone']
                    Bathymetry = self.__Simu_Param['arrayInfoLogistic'][
                                                belongsTo]['Bathymetry']
                    Soil_type = self.__Simu_Param['arrayInfoLogistic'][
                                                belongsTo]['Soil type']

                if belongsTo == 'Array':

                    if 'Substation' in ComponentType:
                        ComponentTypeLogistic = 'collection point'
                        ComponentIDLogistic   = ComponentID

                    elif 'subhub' in ComponentType:
                        ComponentTypeLogistic = 'collection point'
                        ComponentIDLogistic   = ComponentID

                    elif 'Export Cable' in ComponentType:
                        ComponentTypeLogistic = 'static cable'
                        ComponentIDLogistic   = \
                                        int(ComponentID[-3:len(ComponentID)])

                    else:
                        ComponentTypeLogistic = ComponentType
                        ComponentIDLogistic   = ComponentID

                else:

                    # Adjustmet of the names to logistic
                    # The name of subsystems in logistic and RAM are differnt
                    if 'Dynamic cable' in ComponentSubType:
                        ComponentTypeLogistic = 'dynamic cable'
                        # problem with logistic database
                        ComponentIDLogistic   = 0

                    elif 'Mooring line' in ComponentSubType:
                        ComponentTypeLogistic = 'mooring line'
                        ComponentIDLogistic   = \
                                        int(ComponentID[-3:len(ComponentID)])

                    elif 'Foundation' in ComponentSubType:
                        ComponentTypeLogistic = 'foundation'
                        ComponentIDLogistic   = ComponentID

                    else:
                        ComponentTypeLogistic = ComponentType
                        ComponentIDLogistic   = ComponentID

                    if 'device' in ComponentTypeLogistic:
                        ComponentTypeLogistic = 'device'


                # Calc logistic functions
                start_time_logistic = timeit.default_timer()

                # Values for logistic
                values = [FM_ID,
                          ComponentTypeLogistic,
                          ComponentSubType,
                          ComponentIDLogistic,
                          depth,
                          x_coord,
                          y_coord,
                          zone,
                          repairActionDateStr,
                          d_acc,
                          d_om,
                          str(helideck),
                          Hs_acc,
                          Tp_acc,
                          Ws_acc,
                          Cs_acc,
                          Hs_om,
                          Tp_om,
                          Ws_om,
                          Cs_om,
                          technician,
                          sp_dry_mass,
                          sp_length,
                          sp_width,
                          sp_height,
                          Dist_port,
                          Port_Index,
                          Bathymetry,
                          Soil_type,
                          self.__PrepTimeCalcUnCoMa
                          ]

                #self.__om_logistic_outputs = pd.DataFrame(index=[0],columns=keys)
                self.__wp6_outputsForLogistic.ix[0] = values

                # apply dafety factors in vessels parameters
                (ports,
                 vessels,
                 equipments) = safety_factors(copy.deepcopy(self.__ports),
                                              copy.deepcopy(self.__vessels),
                                              copy.deepcopy(self.__equipments),
                                              copy.deepcopy(self.__port_sf),
                                              copy.deepcopy(self.__vessel_sf),
                                              copy.deepcopy(self.__eq_sf))

                # Collecting relevant port information
                om_port_index = \
                    self.__wp6_outputsForLogistic['Port_Index [-]'].ix[0]

                om_port = {}
                om_port['Selected base port for installation'] = \
                                                    ports.ix[om_port_index]

#                """
#                 Initialising logistic operations and logistic phase
#                """
                logOp = logOp_init(self.__schedule_OLC)

                logPhase_om = logPhase_om_init(logOp,
                                               vessels,
                                               equipments,
                                               self.__wp6_outputsForLogistic)

                # Select the suitable Log phase id
                log_phase_id = logPhase_select(self.__wp6_outputsForLogistic)
                log_phase = logPhase_om[log_phase_id]
                log_phase.op_ve_init = log_phase.op_ve

#                """
#                 Assessing the O&M logistic phase requested
#                """

                # Initialising the output dictionary to be passed to the O&M
                # module
                om_log = {'port': om_port,
                          'requirement': {},
                          'eq_select': {},
                          've_select': {},
                          'combi_select': {},
                          'schedule': {},
                          'cost': {},
                          'optimal': {},
                          'risk': {},
                          'envir': {},
                          'findSolution': {}
                          }

                # Characterizing the logistic requirements
                om_log['requirement'] = feas_om(log_phase,
                                                log_phase_id,
                                                self.__wp6_outputsForLogistic,
                                                self.__device,
                                                self.__sub_device,
                                                self.__collection_point,
                                                self.__connectors,
                                                self.__dynamic_cable,
                                                self.__static_cable)

                # Selecting the maritime infrastructure satisfying the logistic requirements
                om_log['eq_select'], log_phase = select_e(om_log, log_phase)
                om_log['ve_select'], log_phase = select_v(om_log, log_phase)

                # Matching requirements to ensure compatiblity of combinations of
                # port/vessel(s)/equipment leading to feasible logistic solutions
                port = om_port['Selected base port for installation']

                (om_log['combi_select'],
                 log_phase,
                 MATCH_FLAG) = compatibility_ve(om_log,
                                                log_phase,
                                                port)

                stop_time_logistic = timeit.default_timer()
                if MATCH_FLAG == 'NoSolutions':
                    ves_req = {'deck area [m^2]':
                                   om_log['requirement'][5]['deck area'],
                               'deck cargo [t]':
                                   om_log['requirement'][5]['deck cargo'],
                               'deck loading [t/m^2]':
                                   om_log['requirement'][5]['deck loading']
                               }

                    indexNoSolutionsFound.append([iCnt,
                                                  ves_req,
                                                  sp_dry_mass,
                                                  sp_length,
                                                  sp_width,
                                                  sp_height])

                    if self.__dtocean_maintenance_PRINT_FLAG == True:
                        print 'WP6: loop = ', loop
                        print 'WP6: ComponentID = ', ComponentID
                        print 'WP6: RA_ID = ', RA_ID
                        print 'WP6: FM_ID = ', FM_ID
                        print 'WP6: values = ', values
                        print 'NoSolution'
                        print 'calcLogistic: Simulation Duration [s]: ' + \
                                str(stop_time_logistic - start_time_logistic)
                        print ''
                        print ''
#                '''else:
#                    if self.__dtocean_maintenance_PRINT_FLAG == True:
#                        print 'WP6: loop = ', loop
#                        print 'WP6: ComponentID = ', ComponentID
#                        print 'WP6: RA_ID = ', RA_ID
#                        print 'WP6: FM_ID = ', FM_ID
#                        print 'WP6: values = ', values
#                        print 'Solution'
#                        print 'calcLogistic: Simulation Duration [s]: ' + str(stop_time_logistic - start_time_logistic)
#                        print ''
#                        print '''''

                loop = loop + 1

            if len(indexNoSolutionsFound) != 0:

                self.__errorFlag = True

                for iCnt in range(0,len(indexNoSolutionsFound)):

                    index = indexNoSolutionsFound[iCnt][0]
                    ComponentType = \
                        self.__eventsTableNoPoisson.ComponentType[index]
                    ComponentSubType = \
                        self.__eventsTableNoPoisson.ComponentSubType[index]
                    ComponentID = \
                        self.__eventsTableNoPoisson.ComponentID[index]
                    RA_ID = self.__eventsTableNoPoisson.RA_ID[index]
                    FM_ID = self.__eventsTableNoPoisson.FM_ID[index]
                    deck_area = \
                        indexNoSolutionsFound[iCnt][1]['deck area [m^2]']
                    deck_cargo = \
                        indexNoSolutionsFound[iCnt][1]['deck cargo [t]']
                    deck_loading = \
                        indexNoSolutionsFound[iCnt][1]['deck loading [t/m^2]']
                    sp_dry_mass = indexNoSolutionsFound[iCnt][2]
                    sp_length = indexNoSolutionsFound[iCnt][3]
                    sp_width = indexNoSolutionsFound[iCnt][4]
                    sp_height = indexNoSolutionsFound[iCnt][5]

                    values = ['NoSolutionsFound',
                              ComponentID,
                              ComponentType,
                              ComponentSubType,
                              FM_ID,
                              RA_ID,
                              deck_area,
                              deck_cargo,
                              deck_loading,
                              sp_dry_mass,
                              sp_length,
                              sp_width,
                              sp_height]

                    self.__errorTable.ix[iCnt] = values

        return

    def __calcLCOE_OfArray(self):

        '''__calcLCOE_OfArray function: estimation of the of whole array

        '''

        # calculation of costs
        self.__calcLCOE_OfOM()

        # Calculation after the end of simulation
        self.__postCalculation()

        return

    def __calcLCOE_OfOM(self):

        '''__calcLCOE_OfOM function: estimation of the LCOE of O&M

        '''

        # set the index of the tables to zero
        self.__actIdxOfUnCoMa = 0
        self.__actIdxOfCaBaMa = 0
        self.__actIdxOfCoBaMa = 0

        # set the local loops to zero
        loop = 0
        loopValuesForOutput_CoBaMa = 0
        loopValuesForOutput_CaBaMa = 0
        loopValuesForOutput_UnCoMa = 0

        # total action delay
        self.__totalActionDelayHour = 0

        # actual action delay
        self.__actActionDelayHour = 0

        # set the flags to False
        flagCalcUnCoMa = False
        flagCalcCaBaMa = False
        flagCalcCoBaMa = False

        # Initialisation of the calculation flags
        if self.__Farm_OM['calendar_based_maintenance'] == True:
            flagCalcCaBaMa = True
        elif self.__Farm_OM['corrective_maintenance'] == True:
            flagCalcUnCoMa = True
        elif self.__Farm_OM['condition_based_maintenance'] == True:
            flagCalcCoBaMa = True

        # calculation loop
        while (flagCalcUnCoMa == True or
               flagCalcCaBaMa == True or
               flagCalcCoBaMa == True):

            # condition based maintenance
            # *****************************************************************
            # *****************************************************************
            if (self.__Farm_OM['condition_based_maintenance'] == True and
                flagCalcCoBaMa == True):

                # break condition
                if len(self.__CoBaMa_eventsTable) <= self.__actIdxOfCoBaMa:
                    flagCalcCoBaMa = False
                    continue

                (loop,
                 loopValuesForOutput_CoBaMa,
                 flagCalcCoBaMa) = self.__get_lcoe_condition(
                                                   loop,
                                                   loopValuesForOutput_CoBaMa)

            # calandar based maintenance
            # *****************************************************************
            # *****************************************************************
            if (self.__Farm_OM['calendar_based_maintenance'] == True and
                flagCalcCaBaMa == True):

                (loop,
                 loopValuesForOutput_CaBaMa,
                 flagCalcCoBaMa,
                 flagCalcCaBaMa,
                 flagCalcUnCoMa) = self.__get_lcoe_calendar(
                                                   loop,
                                                   loopValuesForOutput_CaBaMa)

                if self.__actIdxOfCaBaMa == len(self.__CaBaMa_eventsTable):

                    flagCalcCaBaMa = False
                    loop = 0

                    if self.__Farm_OM['corrective_maintenance'] == True:
                        flagCalcUnCoMa = True
                    elif self.__Farm_OM['condition_based_maintenance'] == True:
                        flagCalcCoBaMa = True

                    continue

            # unplaned corrective maintenance
            # *****************************************************************
            # *****************************************************************
            if (self.__Farm_OM['corrective_maintenance'] == True and
                flagCalcUnCoMa == True):

                (loop,
                 loopValuesForOutput_UnCoMa,
                 flagCalcCoBaMa,
                 flagCalcUnCoMa) = self.__get_lcoe_unplanned(
                                                 loop,
                                                 loopValuesForOutput_UnCoMa,
                                                 flagCalcCoBaMa,
                                                 flagCalcUnCoMa)

                if self.__actIdxOfUnCoMa == len(self.__UnCoMa_eventsTable):

                    flagCalcUnCoMa = False
                    loop = 0

                    if self.__Farm_OM['condition_based_maintenance'] == True:
                        flagCalcCoBaMa = True

        return

    def __get_lcoe_condition(self, loop, loopValuesForOutput_CoBaMa):

        start_time_CoBaMa = timeit.default_timer()

        idx = self.__actIdxOfCoBaMa

        currentStartDate = self.__CoBaMa_eventsTable.currentStartDate[idx]
        currentEndDate = self.__CoBaMa_eventsTable.currentEndDate[idx]
        currentAlarmDate =  self.__CoBaMa_eventsTable.currentAlarmDate[idx]
        belongsTo = str(self.__CoBaMa_eventsTable.belongsTo[idx])
        ComponentType = str(self.__CoBaMa_eventsTable.ComponentType[idx])
        ComponentSubType = str(self.__CoBaMa_eventsTable.ComponentSubType[idx])
        ComponentID = str(self.__CoBaMa_eventsTable.ComponentID[idx])
        FM_ID = str(self.__CoBaMa_eventsTable.FM_ID[idx])
        RA_ID = str(self.__CoBaMa_eventsTable.RA_ID[idx])
        threshold = self.__CoBaMa_eventsTable.threshold[idx]
        failureRate = self.__CoBaMa_eventsTable.failureRate[idx]
        flagCaBaMa = self.__CoBaMa_eventsTable.flagCaBaMa[idx]
        indexFM = self.__CoBaMa_eventsTable.indexFM[idx]
        CompIDWithIndex = ComponentID + '_' + str(indexFM)
        currentAlarmDateStr = currentAlarmDate.strftime(self.__strFormat1)
        failureDate = currentAlarmDate
        nowindow = self.__arrayDict[ComponentID]['CoBaMaNoWeatherWindow']

        self.__repairActionDate = datetime.datetime.strptime(
                                                        str(currentAlarmDate),
                                                        self.__strFormat2)

        # break condition
        '''if self.__endOperationDate <= currentAlarmDate:
            flagCalcCoBaMa = False
            continue'''

        # simulate or not
        simulateFlag = True

        if self.__NrOfDevices == self.__NrOfTurnOutDevices:

            simulateFlag = False

        else:

          # Set the simulateFlag?
            if belongsTo == 'Array':

                if nowindow:
                    simulateFlag = False

            else:

                if 'device' in ComponentType and nowindow:
                    simulateFlag = False

        if simulateFlag == False:

            self.__actIdxOfCoBaMa = self.__actIdxOfCoBaMa + 1

            if self.__actIdxOfCoBaMa == len(self.__CoBaMa_eventsTable):
                flagCalcCoBaMa = False
                loop = 0

            return loop, loopValuesForOutput_CoBaMa, flagCalcCoBaMa

        if self.__dtocean_maintenance_PRINT_FLAG == True:

            print 'WP6: ******************************************************'
            print 'WP6: actIdxOfCoBaMa = ', self.__actIdxOfCoBaMa
            print 'WP6: ComponentID    = ', ComponentID
            print 'WP6: RA_ID = ', RA_ID
            print 'WP6: FM_ID = ', FM_ID

        # Calculate the cost of operation at alarm date
        # independent from inspection or repair action
        sp_dry_mass = self.__Failure_Mode[CompIDWithIndex]['spare_mass']
        sp_length   = self.__Failure_Mode[CompIDWithIndex]['spare_length']
        sp_width    = self.__Failure_Mode[CompIDWithIndex]['spare_width']
        sp_height   = self.__Failure_Mode[CompIDWithIndex]['spare_height']

        if 'Insp' in FM_ID:
            series = self.__Inspection[CompIDWithIndex]
            action = 'inspection'
        else:
            series = self.__Repair_Action[CompIDWithIndex]
            action = 'repair'

        # for logistic
        d_acc = series['duration_accessibility']
        d_om = series['duration_maintenance']
        helideck = self.__Farm_OM['helideck']
        Hs_acc = series['wave_height_max_acc']
        Tp_acc = series['wave_periode_max_acc']
        Ws_acc = series['wind_speed_max_acc']
        Cs_acc = series['current_speed_max_acc']
        Hs_om = series['wave_height_max_om']
        Tp_om = series['wave_periode_max_om']
        Ws_om = series['wind_speed_max_om']
        Cs_om = series['current_speed_max_om']
        technician = series['number_technicians'] + \
                                                series['number_specialists']

        Dist_port = self.__portDistIndex[action][0]
        Port_Index = self.__portDistIndex[action][1]

        if belongsTo == 'Array':
            series = self.__Simu_Param['arrayInfoLogistic'][ComponentID]
        else:
            series = self.__Simu_Param['arrayInfoLogistic'][belongsTo]

        depth = series['depth']
        x_coord = series['x coord']
        y_coord = series['y coord']
        zone = series['zone']
        Bathymetry = series['Bathymetry']
        Soil_type = series['Soil type']

        if belongsTo == 'Array':

            if 'Substation' in ComponentType:
                ComponentTypeLogistic = 'collection point'
                ComponentIDLogistic   = ComponentID

            elif 'subhub' in ComponentType:
                ComponentTypeLogistic = 'collection point'
                ComponentIDLogistic   = ComponentID

            elif 'Export Cable' in ComponentType:
                ComponentTypeLogistic = 'static cable'
                ComponentIDLogistic   = int(ComponentID[-3:len(ComponentID)])

            else:
                ComponentTypeLogistic = ComponentType
                ComponentIDLogistic   = ComponentID

        else:

            # Adjustmet of the names to logistic
            # The name of subsystems in logistic and RAM are differnt
            if 'Dynamic cable' in ComponentSubType:
                ComponentTypeLogistic = 'dynamic cable'
                # problem with logistic database
                ComponentIDLogistic   = 0#int(ComponentID[-3:len(ComponentID)])

            elif 'Mooring line' in ComponentSubType:
                ComponentTypeLogistic = 'mooring line'
                ComponentIDLogistic   = int(ComponentID[-3:len(ComponentID)])

            elif 'Foundation' in ComponentSubType:
                ComponentTypeLogistic = 'foundation'
                ComponentIDLogistic   = ComponentID

            else:
                ComponentTypeLogistic = ComponentType
                ComponentIDLogistic   = ComponentID

            if 'device' in ComponentTypeLogistic:
                ComponentTypeLogistic = 'device'

        # Values for logistic
        values = [FM_ID,
                  ComponentTypeLogistic,
                  ComponentSubType,
                  ComponentIDLogistic,
                  depth,
                  x_coord,
                  y_coord,
                  zone,
                  currentAlarmDateStr,
                  d_acc,
                  d_om,
                  str(helideck),
                  Hs_acc,
                  Tp_acc,
                  Ws_acc,
                  Cs_acc,
                  Hs_om,
                  Tp_om,
                  Ws_om,
                  Cs_om,
                  technician,
                  sp_dry_mass,
                  sp_length,
                  sp_width,
                  sp_height,
                  Dist_port,
                  Port_Index,
                  Bathymetry,
                  Soil_type,
                  self.__PrepTimeCalcCoBaMa]

        self.__wp6_outputsForLogistic.ix[0] = values

        # Calc logistic functions
        start_time_logistic = timeit.default_timer()
        self.__calcLogistic()
        stop_time_logistic = timeit.default_timer()

        if self.__dtocean_maintenance_PRINT_FLAG == True:
            print 'calcLogistic: Simulation Duration [s]: ' + \
                                str(stop_time_logistic - start_time_logistic)

        if self.__om_logistic['findSolution'] == 'NoSolutionsFound':

            if self.__dtocean_maintenance_PRINT_FLAG == True:
                print 'WP6: ErrorID = NoSolutionsFound!'
                print 'WP6: values = ', values

            # increase the index
            self.__actIdxOfCoBaMa = self.__actIdxOfCoBaMa + 1

            # time consumption CaBaMa
            stop_time_CoBaMa = timeit.default_timer()
            duration = (stop_time_CoBaMa - start_time_CoBaMa) - \
                                    (stop_time_logistic - start_time_logistic)

            if self.__dtocean_maintenance_PRINT_FLAG == True:
                print 'calcCoBaMa: Simulation Duration [s]: ' + str(duration)

            return loop, loopValuesForOutput_CoBaMa, flagCalcCoBaMa

        if (self.__om_logistic['findSolution'] == 'NoWeatherWindowFound' and
            not self.__ignoreWeatherWindow):

            if self.__dtocean_maintenance_PRINT_FLAG == True:
                print 'WP6: ErrorID = NoWeatherWindowFound!'
                print 'WP6: values = ', values

            # increase the index
            self.__actIdxOfCoBaMa = self.__actIdxOfCoBaMa + 1

            # time consumption CaBaMa
            stop_time_CoBaMa = timeit.default_timer()
            duration = (stop_time_CoBaMa - start_time_CoBaMa) - \
                                    (stop_time_logistic - start_time_logistic)

            if self.__dtocean_maintenance_PRINT_FLAG == True:
                print 'calcCoBaMa: Simulation Duration [s]: ' + str(duration)

            return loop, loopValuesForOutput_CoBaMa, flagCalcCoBaMa

        CaBaMaSolution = False

        if self.__ignoreWeatherWindow:

            downtimesecs = (self.__endOperationDate -
                                                failureDate).total_seconds()

            optLogisticCostValue = 0
            omCostValueSpare = 0
            omCostValue = 0
            totalDownTimeHours = downtimesecs // 3600
            self.__departOpDate = self.__endOperationDate

        else:

            optimal = self.__om_logistic['optimal']

            self.__endOpDate = datetime.datetime(optimal['end_dt'].year,
                                                 optimal['end_dt'].month,
                                                 optimal['end_dt'].day,
                                                 optimal['end_dt'].hour,
                                                 optimal['end_dt'].minute)


            # In LpM7 case self.__om_logistic['optimal']['depart_dt'] is a dict
            if type(optimal['depart_dt']) == dict:
                dummy__departOpDate = optimal['depart_dt'][
                                        'weather windows depart_dt_replace']
                dummy__departOpDate = optimal['depart_dt'][
                                        'weather windows depart_dt_retrieve']
            else:
                dummy__departOpDate = optimal['depart_dt']

            self.__departOpDate = datetime.datetime(dummy__departOpDate.year,
                                                    dummy__departOpDate.month,
                                                    dummy__departOpDate.day,
                                                    dummy__departOpDate.hour,
                                                    dummy__departOpDate.minute)

            # total optim cost from logistic
            optLogisticCostValue = optimal['total cost']

#            # Override logistics
#            opsecs = (self.__endOpDate - self.__departOpDate).total_seconds()
#            self.__totalSeaTimeHour = opsecs // 3600
#
#            optimal['schedule sea time'] = self.__totalSeaTimeHour

            self.__totalSeaTimeHour = optimal['schedule sea time']

            downsecs = (self.__endOpDate - currentAlarmDate).total_seconds()
            totalDownTimeHours = downsecs // 3600

            (omCostValueSpare,
             omCostValue) = self.__calcCostOfOM(FM_ID, CompIDWithIndex)

            totalCostCoBaMa = optLogisticCostValue + omCostValue

            # Is there a calandar based maintenance for this Component ID in
            # near future
            if (flagCaBaMa == True or
                (flagCaBaMa == False and
                     self.__Farm_OM['calendar_based_maintenance'] == True)):

                # find the blocks in CaBaMa
                if 'device' in ComponentType:
                    if flagCaBaMa == True:
                        CaBaMaTableQueryDeviceID  = ComponentType
                    else:
                        CaBaMaTableQueryDeviceID  = ComponentType[0:-3]

                    CaBaMaTableQuerySubSystem = ComponentSubType

                elif 'subhub' in ComponentType:
                    if flagCaBaMa == True:
                        CaBaMaTableQueryDeviceID = ComponentType
                    else:
                        CaBaMaTableQueryDeviceID = ComponentType[0:-3]
                else:
                    CaBaMaTableQueryDeviceID  = 'Array'
                    CaBaMaTableQuerySubSystem = ComponentType[0:-3]

                if 'subhub' in ComponentType:

                    dummyCaBaMaTable = self.__CaBaMa_eventsTable.loc[
                            (self.__CaBaMa_eventsTable['ComponentType'] == \
                                                CaBaMaTableQueryDeviceID) & \
                            (self.__CaBaMa_eventsTable['FM_ID'] == FM_ID) & \
                            (self.__CaBaMa_eventsTable['indexFM'] == indexFM)]

                else:

                    dummyCaBaMaTable = self.__CaBaMa_eventsTable.loc[
                        (self.__CaBaMa_eventsTable['RA_ID'] == RA_ID) & \
                        (self.__CaBaMa_eventsTable['ComponentSubType'] == \
                                           CaBaMaTableQuerySubSystem) & \
                         (self.__CaBaMa_eventsTable['FM_ID'] == FM_ID) & \
                         (self.__CaBaMa_eventsTable['indexFM'] == indexFM)]

                indexDummyCaBaMaTable = 0

                # currently only for device. The components of the array will
                # be repaired immediately
                if 1 < len(dummyCaBaMaTable) and 'device' in ComponentType:

                    (CaBaMaSolution,
                     dummyCaBaMaEndDate) = self.__switch_to_calendar(
                                                             CaBaMaSolution,
                                                             dummyCaBaMaTable,
                                                             ComponentID,
                                                             currentAlarmDate,
                                                             currentEndDate,
                                                             totalCostCoBaMa)

        if CaBaMaSolution == True:

            newLineCurrentStartDate = \
                dummyCaBaMaTable.currentEndActionDate[indexDummyCaBaMaTable]

            if flagCaBaMa == True:

                # This component should be repaired in calandar based
                # maintenance in near future.

                # Save the cost of operation
                if belongsTo == 'Array':

                    # Cost
                    self.__arrayDict[ComponentID][
                                    'CoBaMaDeratingCostLogistic'].append(0)
                    self.__arrayDict[ComponentID][
                                    'CoBaMaDeratingCostOM'].append(0)

                else:

                    if 'device' in ComponentType:

                        # Inspection cost
                        self.__arrayDict[ComponentType][
                                'CoBaMaCostDeratingLogistic'].append(0)
                        self.__arrayDict[ComponentType][
                                'CoBaMaDeratingCostOM'].append(0)

                # Save the information about failure and down time in devices
                keys = self.__arrayDict.keys()
                breakdown = self.__arrayDict[ComponentID]['Breakdown']

                for iCnt1 in range(0, len(keys)):

                    if not ('device' in keys[iCnt1] and
                            ('All' in breakdown or keys[iCnt1] in breakdown)):

                        continue

                    # Save the information about failure
                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingOpEvents'].append(currentStartDate)

                    enddate = dummyCaBaMaTable.currentEndActionDate[
                                                        indexDummyCaBaMaTable]
                    secs = (enddate - dummyCaBaMaEndDate).total_seconds()
                    totalDownTimeHours = secs // 3600
                    idstr = str(ComponentID)

                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingOpEventsDuration'].append(
                                                            totalDownTimeHours)
                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingOpEventsIndexFM'].append(indexFM)
                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingOpEventsCausedBy'].append(idstr)

                    if 'device' in ComponentType: continue

                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingCostLogistic'].append(0.0)
                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingCostOM'].append(0.0)

            if (flagCaBaMa == False and
                self.__Farm_OM['calendar_based_maintenance'] == True):

                # This component should be repaired with other same components
                # in calandar based maintenance in near future

                # Save the cost of operation
                if belongsTo == 'Array':

                    # Cost
                    logisticcost = dummyCaBaMaTable.logisticCost[
                                                        indexDummyCaBaMaTable]
                    omcost = dummyCaBaMaTable.omCost[indexDummyCaBaMaTable]

                    self.__arrayDict[ComponentID][
                            'CoBaMaDeratingCostLogistic'].append(logisticcost)
                    self.__arrayDict[ComponentID][
                            'CoBaMaCostOM'].append(omcost)

                    self.__arrayDict[ComponentType][
                            'CoBaMaDeratingCostLogistic'].append(0)
                    self.__arrayDict[ComponentType][
                            'CoBaMaDeratingCostOM'].append(0)

                elif 'device' in ComponentType:

                    # Inspection cost
                    logisticcost = dummyCaBaMaTable.logisticCost[
                                                        indexDummyCaBaMaTable]
                    omcost = dummyCaBaMaTable.omCost[indexDummyCaBaMaTable]

                    self.__arrayDict[ComponentType][
                            'CoBaMaDeratingCostLogistic'].append(logisticcost)
                    self.__arrayDict[ComponentType][
                            'CoBaMaDeratingCostOM'].append(omcost)

                # Save the information about failure and down time in devices
                keys = self.__arrayDict.keys()

                for iCnt1 in range(0, len(keys)):

                    if not ('device' in keys[iCnt1] and
                            ('All' in breakdown or keys[iCnt1] in breakdown)):

                        continue

                    # Save the information about failure
                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingOpEvents'].append(currentStartDate)

                    enddate = dummyCaBaMaTable.currentEndActionDate[
                                                        indexDummyCaBaMaTable]
                    secs = (enddate - dummyCaBaMaEndDate).total_seconds()
                    totalDownTimeHours = secs // 3600
                    idstr = str(ComponentID)

                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingOpEventsDuration'].append(
                                                            totalDownTimeHours)
                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingOpEventsIndexFM'].append(indexFM)
                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingOpEventsCausedBy'].append(idstr)

                    if 'device' in ComponentType: continue

                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingCostLogistic'].append(0.0)
                    self.__arrayDict[keys[iCnt1]][
                            'CoBaMaDeratingCostOM'].append(0.0)

        else:

            newLineCurrentStartDate = self.__endOpDate

            # Save the cost of operation
            if belongsTo == 'Array':

                # Cost
                logisticcost = round(optLogisticCostValue, 2)
                omcost = round(omCostValue, 2)

                self.__arrayDict[ComponentID][
                        'CoBaMaCostLogistic'].append(logisticcost)
                self.__arrayDict[ComponentID]['CoBaMaCostOM'].append(omcost)

                #self.__arrayDict[ComponentType]['CoBaMaCostLogistic'].append(0)
                #self.__arrayDict[ComponentType]['CoBaMaCostOM'].append(0)

            elif 'device' in ComponentType:

                # Inspection cost
                logisticcost = round(optLogisticCostValue, 2)
                omcost = round(omCostValue, 2)

                self.__arrayDict[ComponentType][
                        'CoBaMaCostLogistic'].append(logisticcost)
                self.__arrayDict[ComponentType]['CoBaMaCostOM'].append(omcost)

            # Save the information about failure and down time in devices
            downtimeDeviceList = []
            keys = self.__arrayDict.keys()

            for iCnt1 in range(0,len(keys)):

                nowindow = self.__arrayDict[keys[iCnt1]][
                                                    'CoBaMaNoWeatherWindow']

                if not (not nowindow and
                        'device' in keys[iCnt1] and
                        ('All' in breakdown or keys[iCnt1] in breakdown)):

                    continue

                if (self.__om_logistic['findSolution'] ==
                                            'NoWeatherWindowFound' and
                    self.__ignoreWeatherWindow == False):

                    self.__arrayDict[keys[iCnt1]][
                                            'CoBaMaNoWeatherWindow'] = True
                    self.__NrOfTurnOutDevices = self.__NrOfTurnOutDevices + 1

                downtimeDeviceList.append(str(keys[iCnt1]))

                # Save the information about failure
                self.__arrayDict[keys[iCnt1]][
                        'CoBaMaOpEvents'].append(failureDate)
                self.__arrayDict[keys[iCnt1]][
                        'CoBaMaOpEventsDuration'].append(totalDownTimeHours)
                self.__arrayDict[keys[iCnt1]][
                        'CoBaMaOpEventsIndexFM'].append(indexFM)
                self.__arrayDict[keys[iCnt1]][
                        'CoBaMaOpEventsCausedBy'].append(str(ComponentID))

                if 'device' in ComponentType: continue

                self.__arrayDict[keys[iCnt1]]['CoBaMaCostLogistic'].append(0.0)
                self.__arrayDict[keys[iCnt1]]['CoBaMaCostOM'].append(0.0)
                self.__arrayDict[ComponentID]['CoBaMaNoWeatherWindow'] = True

        if (CaBaMaSolution == False or
            (flagCaBaMa == False and
                 self.__Farm_OM['calendar_based_maintenance'] == True)):

            alarmstr = str(datetime.datetime.strptime(str(currentAlarmDate),
                                                      self.__strFormat2))

            valuesForOutput = [failureRate,
                               alarmstr,
                               alarmstr,
                               str(self.__departOpDate.replace(second=0)),
                               int(totalDownTimeHours),
                               '',
                               ComponentType,
                               ComponentSubType,
                               ComponentID,
                               FM_ID,
                               RA_ID,
                               indexFM,
                               int(optLogisticCostValue),
                               int(omCostValue-omCostValueSpare),
                               int(omCostValueSpare)]

            self.__CoBaMa_outputEventsTable.ix[
                                loopValuesForOutput_CoBaMa] = valuesForOutput
            self.__CoBaMa_outputEventsTable.loc[
                                loopValuesForOutput_CoBaMa,
                                'downtimeDeviceList [-]'] = downtimeDeviceList

            # loopValuesForOutput
            loopValuesForOutput_CoBaMa = loopValuesForOutput_CoBaMa + 1

            if self.__om_logistic['findSolution'] == 'SolutionFound':

                # for environmental team
                self.__env_assess(loop,
                                  failureDate,
                                  FM_ID,
                                  RA_ID,
                                  optimal['schedule sea time'],
                                  'CoBaMa')

                # loop
                loop = loop + 1

                # calculate the new entry in self.__CoBaMa_eventsTable
                index = -1
                series = self.__arrayDict[ComponentID][
                                    'CoBaMa_initOpEventsList'][indexFM - 1]

                for iCnt2 in range(0, len(series)):

                    if (newLineCurrentStartDate < series[iCnt2] and
                        currentEndDate < series[iCnt2]):

                        index = iCnt2
                        break

                if index == -1:

                    errStr = "index is -1, which is also bad"
                    raise RuntimeError(errStr)

                lidx = len(self.__CoBaMa_eventsTable)
                pidx = lidx - 1

                current = self.__CoBaMa_eventsTable.iloc[
                                                self.__actIdxOfCoBaMa, :]

                # new line for the extension of CoBaMa
                self.__CoBaMa_eventsTable.ix[lidx] = copy.deepcopy(current)

                newLineCurrentEndDate = series[index]

                secs = (newLineCurrentEndDate -
                                newLineCurrentStartDate).total_seconds()
                hours = secs / 3600
                shift = hours * (1.0 - threshold)

                newLineCurrentAlarmDate = newLineCurrentStartDate + \
                                                    timedelta(hours=shift)

                self.__CoBaMa_eventsTable.loc[pidx, 'currentStartDate'] = \
                                                newLineCurrentStartDate
                self.__CoBaMa_eventsTable.loc[pidx, 'currentEndDate'] = \
                                                newLineCurrentEndDate
                self.__CoBaMa_eventsTable.loc[pidx, 'currentAlarmDate'] = \
                                                newLineCurrentAlarmDate


                # sort of CoBaMa_eventsTable
                self.__CoBaMa_eventsTable.sort(columns=['currentAlarmDate'],
                                               inplace=True)

                # start index with 0
                self.__CoBaMa_eventsTable.reset_index(drop=True,
                                                      inplace=True)

        # increase the index
        self.__actIdxOfCoBaMa = self.__actIdxOfCoBaMa + 1

        # time consumption CaBaMa
        stop_time_CoBaMa = timeit.default_timer()
        duration = (stop_time_CoBaMa - start_time_CoBaMa) - \
                                (stop_time_logistic - start_time_logistic)

        if self.__dtocean_maintenance_PRINT_FLAG == True:
            print 'calcCoBaMa: Simulation Duration [s]: ' + str(duration)

        return loop, loopValuesForOutput_CoBaMa, flagCalcCoBaMa

    def __switch_to_calendar(self, CaBaMaSolution,
                                   dummyCaBaMaTable,
                                   ComponentID,
                                   currentAlarmDate,
                                   currentEndDate,
                                   totalCostCoBaMa):

        # start index with 0
        dummyCaBaMaTable.reset_index(drop=True,
                                     inplace=True)

        for iCnt in range(0, len(dummyCaBaMaTable)):

            secs = (dummyCaBaMaTable.currentStartActionDate[iCnt] -
                                            currentAlarmDate).total_seconds()
            timeTillStartCaBaMaHour = secs // 3600

            if (timeTillStartCaBaMaHour <
                                self.__timeExtensionDeratingCoBaMaHour):

                indexDummyCaBaMaTable = iCnt
                break

        if indexDummyCaBaMaTable == 0:

            errStr = "indexDummyCaBaMaTable is 0, which is bad, apparently."
            raise RuntimeError(errStr)

        # Benefit CoBaMa
        dummyCoBaMaEndDate = \
            dummyCaBaMaTable.currentStartActionDate[indexDummyCaBaMaTable]

        if currentEndDate <= dummyCoBaMaEndDate:
            dummyCoBaMaEndDate = currentEndDate

        startdate = \
            dummyCaBaMaTable.currentStartActionDate[indexDummyCaBaMaTable]

        secs = (startdate - dummyCoBaMaEndDate).total_seconds()
        dummyCoBaMaTime = secs // 3600

        timeyears = dummyCoBaMaTime / (self.__yearDays * self.__dayHours)
        devnumber = int(ComponentID[-3:len(ComponentID)])
        devenergy = self.__annual_Energy_Production_perD[devnumber]
        dummyCoBaMaEnergyYield = timeyears * devenergy

        dummyCoBaMaMoney = (dummyCoBaMaEnergyYield / 1000.0) * \
                                    self.__Farm_OM['energy_selling_price']
        dummyCoBaMaBenefit = dummyCoBaMaMoney - totalCostCoBaMa

        # Benefit CaBaMa
        dummyCaBaMaEndDate = dummyCoBaMaEndDate + \
                        timedelta(hours=self.__timeExtensionDeratingCoBaMaHour)

        if startdate <= dummyCaBaMaEndDate:
            dummyCaBaMaEndDate = startdate

        secs = (startdate - dummyCaBaMaEndDate).total_seconds()
        dummyCaBaMaTime = secs // 3600

        timeyears = dummyCaBaMaTime / (self.__yearDays * self.__dayHours)
        dummyCaBaMaEnergyYield = timeyears * devenergy

        dummyCaBaMaEnergyYield = dummyCaBaMaEnergyYield * \
                                        (self.__powerDeratingCoBaMa / 100.0)
        dummyCaBaMaMoney = (dummyCaBaMaEnergyYield / 1000.0) * \
                                        self.__Farm_OM['energy_selling_price']
        totalCostCaBaMa = \
            dummyCaBaMaTable.logisticCost[indexDummyCaBaMaTable] + \
                dummyCaBaMaTable.omCost[indexDummyCaBaMaTable]

        dummyCaBaMaBenefit = dummyCaBaMaMoney - totalCostCaBaMa

        # CoBaMa
        if dummyCoBaMaBenefit <= dummyCaBaMaBenefit:
            CaBaMaSolution = True

        return CaBaMaSolution, dummyCaBaMaEndDate

    def __get_lcoe_calendar(self, loop, loopValuesForOutput_CaBaMa):

        start_time_CaBaMa = timeit.default_timer()

        idx = self.__actIdxOfCaBaMa

        startActionDate  = self.__CaBaMa_eventsTable.startActionDate[idx]
        belongsTo        = str(self.__CaBaMa_eventsTable.belongsTo[idx])
        ComponentType    = str(self.__CaBaMa_eventsTable.ComponentType[idx])
        ComponentSubType = str(self.__CaBaMa_eventsTable.ComponentSubType[idx])
        FM_ID            = str(self.__CaBaMa_eventsTable.FM_ID[idx])
        indexFM          = self.__CaBaMa_eventsTable.indexFM[idx]
        RA_ID            = str(self.__CaBaMa_eventsTable.RA_ID[idx])
        ComponentID      = str(self.__CaBaMa_eventsTable.ComponentID[idx])
        shortid          = int(ComponentID[-3:len(ComponentID)])

        # find the blocks in CaBaMa
        if 'device' in ComponentType:
            CaBaMaTableQueryDeviceID  = ComponentType
            CaBaMaTableQuerySubSystem = ComponentSubType

        elif 'subhub' in ComponentType:
            CaBaMaTableQueryDeviceID = ComponentType

        else:
            CaBaMaTableQueryDeviceID  = 'Array'
            CaBaMaTableQuerySubSystem = ComponentType[0:-3]

        if 'subhub' in ComponentType:

            dummyCaBaMaTable = self.__CaBaMa_eventsTable.loc[
                (self.__CaBaMa_eventsTable['ComponentType'] ==
                                                CaBaMaTableQueryDeviceID) & \
                (self.__CaBaMa_eventsTable['startActionDate'] ==
                                                startActionDate) & \
                (self.__CaBaMa_eventsTable['FM_ID'] == FM_ID) & \
                (self.__CaBaMa_eventsTable['indexFM'] == indexFM)]

        else:

            dummyCaBaMaTable = self.__CaBaMa_eventsTable.loc[
                (self.__CaBaMa_eventsTable['RA_ID'] == RA_ID) & \
                (self.__CaBaMa_eventsTable['ComponentSubType'] ==
                                                 CaBaMaTableQuerySubSystem) & \
                (self.__CaBaMa_eventsTable['startActionDate'] ==
                                                 startActionDate) & \
                (self.__CaBaMa_eventsTable['FM_ID'] == FM_ID) & \
                (self.__CaBaMa_eventsTable['indexFM'] == indexFM)]

        # start index with 0
        dummyCaBaMaTable.reset_index(drop=True, inplace=True)

        blockNumberList = []
        divModBlockNumber = divmod(len(dummyCaBaMaTable),
                                   self.__CaBaMa_nrOfMaxActions)

        if 0 < divModBlockNumber[0]:

            for iCnt in range(0,divModBlockNumber[0]):

                blockNumberList.append(self.__CaBaMa_nrOfMaxActions)

                if iCnt == divModBlockNumber[0] - 1:
                    blockNumberList.append(divModBlockNumber[1])

        else:

            blockNumberList.append(divModBlockNumber[1])

        for iCnt in range(0, len(blockNumberList)):

            bidx = iCnt * self.__CaBaMa_nrOfMaxActions

            blockNumber = blockNumberList[iCnt]
            currentStartActionDate = \
                                dummyCaBaMaTable.currentStartActionDate[bidx]

            actiondt = datetime.datetime.strptime(str(currentStartActionDate),
                                                  self.__strFormat2)
            currentStartActionDateFormat2 = actiondt

            # Date of logistic request
            self.__repairActionDate = currentStartActionDateFormat2
            repairActionDateStr = currentStartActionDate.strftime(
                                                            self.__strFormat1)

            if self.__dtocean_maintenance_PRINT_FLAG == True:
                print 'WP6: **************************************************'
                print 'WP6: actIdxOfCaBaMa = ', self.__actIdxOfCaBaMa
                print 'WP6: ComponentID = ', ComponentID
                print 'WP6: RA_ID = ', RA_ID
                print 'WP6: FM_ID = ', FM_ID

            # break the while loop if repairActionDate is greater than
            # self.__endOperationDate
            if self.__endOperationDate < self.__repairActionDate:

                flagCalcCaBaMa = False
                loop = 0

                if self.__Farm_OM['corrective_maintenance']:
                    flagCalcUnCoMa = True
                elif self.__Farm_OM['condition_based_maintenance']:
                    flagCalcCoBaMa = True

                break

            ComponentTypeList = []
            ComponentSubTypeList = []
            ComponentIDList = []

            # loop over blockNumber
            for iCnt1 in range(0, blockNumber):

                bidx1 = bidx + iCnt1

                belongsTo = dummyCaBaMaTable.belongsTo[bidx1]
                ComponentID = dummyCaBaMaTable.ComponentID[bidx1]
                CompIDWithIndex = ComponentID + '_' + str(indexFM)

                ComponentType = dummyCaBaMaTable.ComponentType[bidx1]
                ComponentSubType = dummyCaBaMaTable.ComponentSubType[bidx1]

                ComponentTypeList.append(ComponentType)
                ComponentSubTypeList.append(ComponentSubType)
                ComponentIDList.append(ComponentID)

                if iCnt == 0:

                    failure = self.__Failure_Mode[CompIDWithIndex]

                    # independent from inspection or repair action
                    sp_dry_mass = failure['spare_mass']
                    sp_length = failure['spare_length']
                    sp_width = failure['spare_width']
                    sp_height = failure['spare_height']

                    if 'Insp' in FM_ID:

                        inspection = self.__Inspection[CompIDWithIndex]

                        # For logistic
                        d_acc = inspection['duration_accessibility']
                        d_om = inspection['duration_inspection']
                        helideck = self.__Farm_OM['helideck']
                        Hs_acc = inspection['wave_height_max_acc']
                        Tp_acc = inspection['wave_periode_max_acc']
                        Ws_acc = inspection['wind_speed_max_acc']
                        Cs_acc = inspection['current_speed_max_acc']
                        Hs_om = inspection['wave_height_max_om']
                        Tp_om = inspection['wave_periode_max_om']
                        Ws_om = inspection['wind_speed_max_om']
                        Cs_om = inspection['current_speed_max_om']
                        technician = inspection['number_technicians'] + \
                                            inspection['number_specialists']

                        Dist_port = self.__portDistIndex['inspection'][0]
                        Port_Index = self.__portDistIndex['inspection'][1]

                    else:

                        repair = self.__Repair_Action[CompIDWithIndex]

                        # for logistic
                        d_acc = repair['duration_accessibility']
                        d_om = repair['duration_maintenance']
                        helideck = self.__Farm_OM['helideck']
                        Hs_acc = repair['wave_height_max_acc']
                        Tp_acc = repair['wave_periode_max_acc']
                        Ws_acc = repair['wind_speed_max_acc']
                        Cs_acc = repair['current_speed_max_acc']
                        Hs_om = repair['wave_height_max_om']
                        Tp_om = repair['wave_periode_max_om']
                        Ws_om = repair['wind_speed_max_om']
                        Cs_om = repair['current_speed_max_om']
                        technician = repair['number_technicians'] + \
                                                repair['number_specialists']

                        Dist_port = self.__portDistIndex['repair'][0]
                        Port_Index = self.__portDistIndex['repair'][1]


                    if belongsTo == 'Array':

                        if 'Substation' in ComponentType:

                            ComponentTypeLogistic = 'collection point'
                            ComponentIDLogistic = ComponentID

                        elif 'subhub' in ComponentType:

                            ComponentTypeLogistic = 'collection point'
                            ComponentIDLogistic = ComponentID

                        elif 'Export Cable' in ComponentType:

                            ComponentTypeLogistic = 'static cable'
                            ComponentIDLogistic = shortid

                        else:

                            ComponentTypeLogistic = ComponentType
                            ComponentIDLogistic = ComponentID

                    else:

                        # Adjustmet of the names to logistic
                        # The name of subsystems in logistic and RAM are
                        # differnt
                        if 'Dynamic cable' in ComponentSubType:
                            ComponentTypeLogistic = 'dynamic cable'
                            # problem with logistic database
                            ComponentIDLogistic = 0 #shortid

                        elif 'Mooring line' in ComponentSubType:
                            ComponentTypeLogistic = 'mooring line'
                            ComponentIDLogistic = shortid

                        elif 'Foundation' in ComponentSubType:
                            ComponentTypeLogistic = 'foundation'
                            ComponentIDLogistic = ComponentID

                        else:
                            ComponentTypeLogistic = ComponentType
                            ComponentIDLogistic = ComponentID

                        if 'device' in ComponentTypeLogistic:
                            ComponentTypeLogistic = 'device'


                if belongsTo == 'Array':

                    series = self.__Simu_Param['arrayInfoLogistic'][
                                                                ComponentID]

                else:

                    series = self.__Simu_Param['arrayInfoLogistic'][belongsTo]

                depth = series['depth']
                x_coord = series['x coord']
                y_coord = series['y coord']
                zone = series['zone']
                Bathymetry = series['Bathymetry']
                Soil_type = series['Soil type']

                # Values for logistic
                values = [FM_ID,
                          ComponentTypeLogistic,
                          ComponentSubType,
                          ComponentIDLogistic,
                          depth,
                          x_coord,
                          y_coord,
                          zone,
                          repairActionDateStr,
                          d_acc,
                          d_om,
                          str(helideck),
                          Hs_acc,
                          Tp_acc,
                          Ws_acc,
                          Cs_acc,
                          Hs_om,
                          Tp_om,
                          Ws_om,
                          Cs_om,
                          technician,
                          sp_dry_mass,
                          sp_length,
                          sp_width,
                          sp_height,
                          Dist_port,
                          Port_Index,
                          Bathymetry,
                          Soil_type,
                          self.__PrepTimeCalcCaBaMa
                          ]

                self.__wp6_outputsForLogistic.ix[iCnt1] = values

                # end of calandar based maintenance
                self.__actIdxOfCaBaMa = self.__actIdxOfCaBaMa + 1

            # Calc logistic functions
            start_time_logistic = timeit.default_timer()
            self.__calcLogistic()
            stop_time_logistic = timeit.default_timer()

            if self.__dtocean_maintenance_PRINT_FLAG == True:
                print 'calcLogistic: Simulation Duration [s]: ' + \
                            str(stop_time_logistic - start_time_logistic)

            # clear wp6_outputsForLogistic
            if blockNumber > 1:

                todrop = range(blockNumber - 1, 0, -1)
                self.__wp6_outputsForLogistic.drop(
                                self.__wp6_outputsForLogistic.index[todrop],
                                inplace=True)

            if (self.__om_logistic['findSolution'] == 'NoSolutionsFound' or
                self.__om_logistic['findSolution'] == 'NoWeatherWindowFound'):

                if self.__dtocean_maintenance_PRINT_FLAG == True:

                    flag = self.__om_logistic['findSolution']

                    if flag == 'NoSolutionsFound':
                         print 'WP6: ErrorID = NoSolutionsFound!'

                    if flag == 'NoWeatherWindowFound':
                         print 'WP6: ErrorID = NoWeatherWindowFound!'

                optLogisticCostValue = 0
                omCostValue = 0
                totalDownTimeHours = 0
                self.__endOpDate = currentStartActionDate

            else:

                optimal = self.__om_logistic['optimal']

                self.__endOpDate = datetime.datetime(optimal['end_dt'].year,
                                                     optimal['end_dt'].month,
                                                     optimal['end_dt'].day,
                                                     optimal['end_dt'].hour,
                                                     optimal['end_dt'].minute)

                # In LpM7 case self.__om_logistic['optimal']['depart_dt'] is a dict
                if type(optimal['depart_dt']) == dict:
                    dummy__departOpDate = optimal['depart_dt'][
                                        'weather windows depart_dt_replace']
                    dummy__departOpDate = optimal['depart_dt'][
                                        'weather windows depart_dt_retrieve']
                else:
                    dummy__departOpDate = optimal['depart_dt']

                self.__departOpDate = datetime.datetime(
                                                    dummy__departOpDate.year,
                                                    dummy__departOpDate.month,
                                                    dummy__departOpDate.day,
                                                    dummy__departOpDate.hour,
                                                    dummy__departOpDate.minute)

                # total optim cost from logistic
                optLogisticCostValue = optimal['total cost']

                # Calculation of total action time (hour)
                # Error in logistic, Therefore calculation in WP6
#                secs = (self.__endOpDate - self.__departOpDate).total_seconds()
#                self.__totalSeaTimeHour = secs // 3600
#                optimal['schedule sea time'] = self.__totalSeaTimeHour

                self.__totalSeaTimeHour = optimal['schedule sea time']

                secs = (self.__endOpDate -
                                currentStartActionDateFormat2).total_seconds()
                totalDownTimeHours = secs // 3600

                (omCostValueSpare,
                 omCostValue) = self.__calcCostOfOM(FM_ID, CompIDWithIndex)

            startdt =  datetime.datetime.strptime(str(currentStartActionDate),
                                                  self.__strFormat2)
            currentStartActionDateFormat2 = startdt
            shiftDate = currentStartActionDateFormat2

            logisticcost = round(optLogisticCostValue / float(blockNumber), 2)
            omcost = round(omCostValue, 2)

            currentStartActionDateList = []

            for iCnt1 in range(0,blockNumber):

                blockshift = self.__totalSeaTimeHour / float(blockNumber)
                tidx = self.__actIdxOfCaBaMa - blockNumber + iCnt1

                shiftDate = shiftDate + timedelta(hours=blockshift)
                self.__CaBaMa_eventsTable.loc[tidx, 'currentEndActionDate'] = \
                                                                    shiftDate

                currentStartActionDateList.append(shiftDate)

                if iCnt1 < blockNumber - 1:
                    self.__CaBaMa_eventsTable.loc[tidx + 1,
                                                  'currentStartActionDate'] = \
                                                                    shiftDate



                self.__CaBaMa_eventsTable.loc[tidx,
                                              'logisticCost'] = logisticcost
                self.__CaBaMa_eventsTable.loc[tidx, 'omCost'] = omcost

            # Save the cost of operation
            if belongsTo == 'Array':

                for iCnt1 in range(0,blockNumber):

                    tidx = iCnt * self.__CaBaMa_nrOfMaxActions + iCnt1

                    # Cost
                    self.__arrayDict[dummyCaBaMaTable.ComponentID[tidx]][
                            'CaBaMaCostLogistic'].append(logisticcost)
                    self.__arrayDict[dummyCaBaMaTable.ComponentID[tidx]][
                            'CaBaMaCostOM'].append(omcost)

            elif 'device' in ComponentType:

                for iCnt1 in range(0,blockNumber):

                    tidx = iCnt * self.__CaBaMa_nrOfMaxActions + iCnt1

                    # Inspection cost
                    self.__arrayDict[dummyCaBaMaTable.ComponentType[tidx]][
                            'CaBaMaCostLogistic'].append(logisticcost)
                    self.__arrayDict[dummyCaBaMaTable.ComponentType[tidx]][
                            'CaBaMaCostOM'].append(omcost)

            # Save the information about failure and down time in devices
            keys = self.__arrayDict.keys()

            for iCnt1 in range(0, len(keys)):

                if not 'device' in keys[iCnt1]: continue

                shiftDate = currentStartActionDateFormat2

                for iCnt2 in range(0, blockNumber):

                    tidx = iCnt * self.__CaBaMa_nrOfMaxActions + iCnt2
                    breakdown = self.__arrayDict[
                            dummyCaBaMaTable.ComponentID[tidx]]['Breakdown']

                    if not ('All' in breakdown or keys[iCnt1] in breakdown):
                        continue

                    # Save the information about failure
                    blockshift = self.__totalSeaTimeHour / float(blockNumber)
                    shiftDate = shiftDate + timedelta(hours=blockshift)
                    blockdown = totalDownTimeHours / float(blockNumber)
                    indexFM = dummyCaBaMaTable.indexFM[tidx]
                    causestr = str(dummyCaBaMaTable.ComponentID[tidx]) + \
                                                                   '_CaBaMa'

                    self.__arrayDict[keys[iCnt1]][
                            'CaBaMaOpEvents'].append(shiftDate)
                    self.__arrayDict[keys[iCnt1]][
                            'CaBaMaOpEventsDuration'].append(blockdown)
                    self.__arrayDict[keys[iCnt1]][
                            'CaBaMaOpEventsIndexFM'].append(indexFM)
                    self.__arrayDict[keys[iCnt1]][
                            'CaBaMaOpEventsCausedBy'].append(causestr)

                    if 'device' in ComponentType: continue

                    self.__arrayDict[keys[iCnt1]][
                            'CaBaMaCostLogistic'].append(0.0)
                    self.__arrayDict[keys[iCnt1]][
                            'CaBaMaCostOM'].append(0.0)

            # Save the information about failure and down time in devices
            downtimeDeviceList = []

            for iCnt2 in range(0,blockNumber):

                tidx = iCnt * self.__CaBaMa_nrOfMaxActions + iCnt2
                breakdown = self.__arrayDict[
                              dummyCaBaMaTable.ComponentID[tidx]]['Breakdown']

                if 'All' in breakdown:

                    dummyList = []
                    keys = self.__arrayDict.keys()

                    for iCnt1 in range(0, len(keys)):

                        if 'device' in keys[iCnt1]:
                            dummyList.append(str(keys[iCnt1]))

                    downtimeDeviceList.append(dummyList)

                else:

                    downtimeDeviceList.append(breakdown)

            # time consumption CaBaMa
            stop_time_CaBaMa = timeit.default_timer()

            if self.__dtocean_maintenance_PRINT_FLAG == True:

                time = (stop_time_CaBaMa - start_time_CaBaMa) - \
                            (stop_time_logistic - start_time_logistic)

                print 'calcCaBaMa: Simulation Duration [s]: ' + str(time)

            if self.__om_logistic['findSolution'] == 'SolutionFound':

                for iCnt1 in range(0, blockNumber):

                    blockhours = int(totalDownTimeHours / float(blockNumber))

                    valuesForOutput = [str(currentStartActionDate),
                                       str(currentStartActionDateList[iCnt1]),
                                       blockhours,
                                       '',
                                       str(ComponentTypeList[iCnt1]),
                                       str(ComponentSubTypeList[iCnt1]),
                                       str(ComponentIDList[iCnt1]),
                                       FM_ID,
                                       RA_ID,
                                       indexFM,
                                       int(optLogisticCostValue),
                                       int(omCostValue - omCostValueSpare),
                                       int(omCostValueSpare)]

                    self.__CaBaMa_outputEventsTable.ix[
                            loopValuesForOutput_CaBaMa] = valuesForOutput
                    self.__CaBaMa_outputEventsTable.loc[
                                            loopValuesForOutput_CaBaMa,
                                            'downtimeDeviceList [-]'] = \
                                                    downtimeDeviceList[iCnt1]

                    loopValuesForOutput_CaBaMa = loopValuesForOutput_CaBaMa + 1

                # for environmental team
                self.__env_assess(loop,
                                  currentStartActionDate,
                                  FM_ID,
                                  RA_ID,
                                  optimal['schedule sea time'],
                                  'CaBaMa')

                loop = loop + 1

        return (loop,
                loopValuesForOutput_CaBaMa,
                flagCalcCoBaMa,
                flagCalcCaBaMa,
                flagCalcUnCoMa)

    def __get_lcoe_unplanned(self, loop,
                                   loopValuesForOutput_UnCoMa,
                                   flagCalcCoBaMa,
                                   flagCalcUnCoMa):

        start_time_UnCoMa = timeit.default_timer()

        # actualIndexOfRepairTable is determined
        # do the the reapir
        idx = self.__actIdxOfUnCoMa

        ComponentType = str(self.__UnCoMa_eventsTable.ComponentType[idx])
        ComponentSubType = str(self.__UnCoMa_eventsTable.ComponentSubType[idx])
        ComponentID = str(self.__UnCoMa_eventsTable.ComponentID[idx])
        RA_ID = str(self.__UnCoMa_eventsTable.RA_ID[idx])
        FM_ID = str(self.__UnCoMa_eventsTable.FM_ID[idx])
        belongsTo = str(self.__UnCoMa_eventsTable.belongsTo[idx])
        failureEvents = self.__UnCoMa_eventsTable.failureEvents[idx]
        repairActionEvents = self.__UnCoMa_eventsTable.repairActionEvents[idx]
        failureRate = self.__UnCoMa_eventsTable.failureRate[idx]

        # simulate or not
        simulateFlag = True

        if self.__NrOfDevices == self.__NrOfTurnOutDevices:

            simulateFlag = False

        else:

            # set the simulateFlag?
            if (belongsTo == 'Array' and
                self.__arrayDict[ComponentID]['UnCoMaNoWeatherWindow']):
                    simulateFlag = False

            elif ('device' in ComponentType and
                  self.__arrayDict[ComponentType]['UnCoMaNoWeatherWindow']):
                    simulateFlag = False

        if simulateFlag == False:

            self.__actIdxOfUnCoMa = self.__actIdxOfUnCoMa + 1

            return (loop,
                    loopValuesForOutput_UnCoMa,
                    flagCalcCoBaMa,
                    flagCalcUnCoMa)

        # delay of repairActionEvents in repair plan
        if self.__totalActionDelayHour < 0:
            shiftDate = self.__UnCoMa_eventsTable.loc[idx,
                                                      'repairActionEvents'] + \
                                  timedelta(hours=-self.__totalActionDelayHour)
            self.__UnCoMa_eventsTable.loc[idx,
                                          'repairActionEvents'] = shiftDate
            repairActionEvents = \
                self.__UnCoMa_eventsTable.repairActionEvents[idx]

        # failureEvents
        failureDate = datetime.datetime.strptime(str(failureEvents),
                                                 self.__strFormat2)

        # Date of logistic request
        repairdate = datetime.datetime.strptime(str(repairActionEvents),
                                                self.__strFormat2)
        self.__repairActionDate = repairdate

        repairActionDateStr = repairActionEvents.strftime(self.__strFormat1)
        indexFM = self.__UnCoMa_eventsTable.indexFM[self.__actIdxOfUnCoMa]
        CompIDWithIndex = ComponentID + '_' + str(indexFM)

        # break the while loop if repairActionDate is greater than
        # self.__endOperationDate
        if self.__endOperationDate < self.__repairActionDate:

            flagCalcUnCoMa = False
            loop = 0

            if self.__Farm_OM['condition_based_maintenance'] == True:
                flagCalcCoBaMa = True

            return (loop,
                    loopValuesForOutput_UnCoMa,
                    flagCalcCoBaMa,
                    flagCalcUnCoMa)

        foundDeleteFlag = False

        # check the impact of CaBaMa of UnCoMa
        if self.__Farm_OM['calendar_based_maintenance'] == True:

            # find the blocks in CaBaMa
            if 'device' in ComponentType:
                CaBaMaTableQueryDeviceID  = ComponentType
                CaBaMaTableQuerySubSystem = ComponentSubType

            elif 'subhub' in ComponentType:
                CaBaMaTableQueryDeviceID = ComponentType

            else:
                CaBaMaTableQueryDeviceID  = 'Array'
                CaBaMaTableQuerySubSystem = ComponentType[0:-3]

            if 'subhub' in ComponentType:

                dummyCaBaMaTable = self.__CaBaMa_eventsTable.loc[
                     (self.__CaBaMa_eventsTable['ComponentType'] == \
                                             CaBaMaTableQueryDeviceID) & \
                     (self.__CaBaMa_eventsTable['FM_ID'] == FM_ID) & \
                     (self.__CaBaMa_eventsTable['indexFM'] == indexFM)]

                if 1 < len(dummyCaBaMaTable):

                    dummyCaBaMaTable.reset_index(drop=True, inplace=True)

                    for iCnt in range(0, len(dummyCaBaMaTable)):

                        enddate = dummyCaBaMaTable.currentEndActionDate[iCnt]
                        secs = (repairActionEvents - enddate).total_seconds()
                        dummyTime = secs // 3600

                        if dummyTime < self.__delayEventsAfterCaBaMaHour:
                            foundDeleteFlag = True
                            break

            else:

                dummyCaBaMaTable = self.__CaBaMa_eventsTable.loc[
                        (self.__CaBaMa_eventsTable['RA_ID'] == RA_ID) & \
                        (self.__CaBaMa_eventsTable['ComponentSubType'] == \
                                             CaBaMaTableQuerySubSystem) & \
                        (self.__CaBaMa_eventsTable['FM_ID'] == FM_ID) & \
                        (self.__CaBaMa_eventsTable['indexFM'] == indexFM)]

                if 1 < len(dummyCaBaMaTable):

                    dummyCaBaMaTable.reset_index(drop=True, inplace=True)

                    for iCnt in range(0, len(dummyCaBaMaTable)):

                        enddate = dummyCaBaMaTable.currentEndActionDate[iCnt]
                        secs = (repairActionEvents - enddate).total_seconds()
                        dummyTime = secs // 3600

                        if dummyTime < self.__delayEventsAfterCaBaMaHour:
                            foundDeleteFlag = True
                            break

        if foundDeleteFlag == True:

            self.__actIdxOfUnCoMa = self.__actIdxOfUnCoMa + 1

            return (loop,
                    loopValuesForOutput_UnCoMa,
                    flagCalcCoBaMa,
                    flagCalcUnCoMa)

        if self.__dtocean_maintenance_PRINT_FLAG == True:

            print 'WP6: ******************************************************'
            print 'WP6: actIdxOfUnCoMa = ', self.__actIdxOfUnCoMa
            print 'WP6: ComponentID = ', ComponentID
            print 'WP6: RA_ID = ', RA_ID
            print 'WP6: FM_ID = ', FM_ID

        # independent from inspection or repair action
        failure = self.__Failure_Mode[CompIDWithIndex]

        sp_dry_mass = failure['spare_mass']
        sp_length = failure['spare_length']
        sp_width = failure['spare_width']
        sp_height = failure['spare_height']

        if 'Insp' in FM_ID:

            # For logistic
            inspection = self.__Inspection[CompIDWithIndex]

            d_acc = inspection['duration_accessibility']
            d_om = inspection['duration_inspection']
            helideck = self.__Farm_OM['helideck']
            Hs_acc = inspection['wave_height_max_acc']
            Tp_acc = inspection['wave_periode_max_acc']
            Ws_acc = inspection['wind_speed_max_acc']
            Cs_acc = inspection['current_speed_max_acc']
            Hs_om = inspection['wave_height_max_om']
            Tp_om = inspection['wave_periode_max_om']
            Ws_om = inspection['wind_speed_max_om']
            Cs_om = inspection['current_speed_max_om']
            technician = inspection['number_technicians'] + \
                                            inspection['number_specialists']

            Dist_port = self.__portDistIndex['inspection'][0]
            Port_Index = self.__portDistIndex['inspection'][1]

        else:

            # for logistic
            repair = self.__Repair_Action[CompIDWithIndex]

            d_acc = repair['duration_accessibility']
            d_om = repair['duration_maintenance']
            helideck = self.__Farm_OM['helideck']
            Hs_acc = repair['wave_height_max_acc']
            Tp_acc = repair['wave_periode_max_acc']
            Ws_acc = repair['wind_speed_max_acc']
            Cs_acc = repair['current_speed_max_acc']
            Hs_om = repair['wave_height_max_om']
            Tp_om = repair['wave_periode_max_om']
            Ws_om = repair['wind_speed_max_om']
            Cs_om = repair['current_speed_max_om']
            technician = repair['number_technicians'] + \
                                            repair['number_specialists']

            Dist_port = self.__portDistIndex['repair'][0]
            Port_Index = self.__portDistIndex['repair'][1]

        if belongsTo == 'Array':
            series = self.__Simu_Param['arrayInfoLogistic'][ComponentID]
        else:
            series = self.__Simu_Param['arrayInfoLogistic'][belongsTo]

        depth = series['depth']
        x_coord = series['x coord']
        y_coord = series['y coord']
        zone = series['zone']
        Bathymetry = series['Bathymetry']
        Soil_type = series['Soil type']

        if belongsTo == 'Array':

            if 'Substation' in ComponentType:
                ComponentTypeLogistic = 'collection point'
                ComponentIDLogistic = ComponentID

            elif 'subhub' in ComponentType:
                ComponentTypeLogistic = 'collection point'
                ComponentIDLogistic = ComponentID

            elif 'Export Cable' in ComponentType:
                ComponentTypeLogistic = 'static cable'
                ComponentIDLogistic = int(ComponentID[-3:len(ComponentID)])

            else:
                ComponentTypeLogistic = ComponentType
                ComponentIDLogistic = ComponentID

        else:

            # Adjustmet of the names to logistic
            # The name of subsystems in logistic and RAM are differnt
            if 'Dynamic cable' in ComponentSubType:
                ComponentTypeLogistic = 'dynamic cable'
                # problem with logistic database
                ComponentIDLogistic = 0#int(ComponentID[-3:len(ComponentID)])

            elif 'Mooring line' in ComponentSubType:
                ComponentTypeLogistic = 'mooring line'
                ComponentIDLogistic = int(ComponentID[-3:len(ComponentID)])

            elif 'Foundation' in ComponentSubType:
                ComponentTypeLogistic = 'foundation'
                ComponentIDLogistic = ComponentID

            else:
                ComponentTypeLogistic = ComponentType
                ComponentIDLogistic = ComponentID

            if 'device' in ComponentTypeLogistic:
                ComponentTypeLogistic = 'device'

        # Values for logistic
        values = [FM_ID,
                  ComponentTypeLogistic,
                  ComponentSubType,
                  ComponentIDLogistic,
                  depth,
                  x_coord,
                  y_coord,
                  zone,
                  repairActionDateStr,
                  d_acc,
                  d_om,
                  str(helideck),
                  Hs_acc,
                  Tp_acc,
                  Ws_acc,
                  Cs_acc,
                  Hs_om,
                  Tp_om,
                  Ws_om,
                  Cs_om,
                  technician,
                  sp_dry_mass,
                  sp_length,
                  sp_width,
                  sp_height,
                  Dist_port,
                  Port_Index,
                  Bathymetry,
                  Soil_type,
                  self.__PrepTimeCalcUnCoMa
                  ]

        self.__wp6_outputsForLogistic.ix[0] = values

        self.__actIdxOfUnCoMa = self.__actIdxOfUnCoMa + 1

        # Calc logistic functions
        start_time_logistic = timeit.default_timer()
        self.__calcLogistic()
        stop_time_logistic = timeit.default_timer()

        if self.__dtocean_maintenance_PRINT_FLAG == True:
            print 'calcLogistic: Simulation Duration [s]: ' + \
                            str(stop_time_logistic - start_time_logistic)

        if self.__om_logistic['findSolution'] == 'NoSolutionsFound':

            if self.__dtocean_maintenance_PRINT_FLAG == True:
                print 'WP6: ErrorID = NoSolutionsFound!'
                print 'WP6: values = ', values

            return (loop,
                    loopValuesForOutput_UnCoMa,
                    flagCalcCoBaMa,
                    flagCalcUnCoMa)

        if self.__om_logistic['findSolution'] == 'NoWeatherWindowFound':

            if self.__dtocean_maintenance_PRINT_FLAG == True:
                print 'WP6: ErrorID = NoWeatherWindowFound!'
                print 'WP6: values = ', values

            if self.__ignoreWeatherWindow:

                secs = (self.__endOperationDate- failureEvents).total_seconds()

                optLogisticCostValue = 0
                omCostValueSpare     = 0
                omCostValue          = 0
                totalDownTimeHours   = secs // 3600
                self.__departOpDate  = self.__endOperationDate

            else:

                return (loop,
                        loopValuesForOutput_UnCoMa,
                        flagCalcCoBaMa,
                        flagCalcUnCoMa)

        else:

            optimal = self.__om_logistic['optimal']

            self.__endOpDate = datetime.datetime(optimal['end_dt'].year,
                                                 optimal['end_dt'].month,
                                                 optimal['end_dt'].day,
                                                 optimal['end_dt'].hour,
                                                 optimal['end_dt'].minute)

            # In LpM7 case self.__om_logistic['optimal']['depart_dt'] is a dict
            if type(optimal['depart_dt']) == dict:
                dummy__departOpDate = optimal['depart_dt'][
                                        'weather windows depart_dt_replace']
                dummy__departOpDate = optimal['depart_dt'][
                                        'weather windows depart_dt_retrieve']
            else:
                dummy__departOpDate = optimal['depart_dt']

            self.__departOpDate = datetime.datetime(dummy__departOpDate.year,
                                                    dummy__departOpDate.month,
                                                    dummy__departOpDate.day,
                                                    dummy__departOpDate.hour,
                                                    dummy__departOpDate.minute)

            # total optim cost from logistic
            optLogisticCostValue = optimal['total cost']

            # should the next operation be shifted? Check self.__repairTable
            if self.__actIdxOfUnCoMa < len(self.__UnCoMa_eventsTable) - 1:

                nidx = self.__actIdxOfUnCoMa + 1
                secs = (self.__UnCoMa_eventsTable.repairActionEvents[nidx] -
                                            self.__endOpDate).total_seconds()

                self.__actActionDelayHour = secs // 3600
                self.__totalActionDelayHour = self.__totalActionDelayHour + \
                                                    self.__actActionDelayHour

            # Calculation of total action time (hour)
            # Error in logistic, Therefore calculation in WP6
#            secs = (self.__endOpDate - self.__departOpDate).total_seconds()
#            self.__totalSeaTimeHour = secs // 3600
#            optimal['schedule sea time'] = self.__totalSeaTimeHour

            self.__totalSeaTimeHour = optimal['schedule sea time']

            secs = (self.__endOpDate - failureDate).total_seconds()
            totalDownTimeHours = secs // 3600

            totalWaitingTimeHours = totalDownTimeHours - \
                                                    self.__totalSeaTimeHour

            (omCostValueSpare,
             omCostValue) = self.__calcCostOfOM(FM_ID, CompIDWithIndex)

        # Save the cost of operation
        logisticcost = round(optLogisticCostValue, 2)
        omcost = round(omCostValue, 2)

        if belongsTo == 'Array':

            # Cost
            self.__arrayDict[ComponentID][
                                    'UnCoMaCostLogistic'].append(logisticcost)
            self.__arrayDict[ComponentID]['UnCoMaCostOM'].append(omcost)

        elif 'device' in ComponentType:

            # Inspection cost
            self.__arrayDict[ComponentType][
                                'UnCoMaCostLogistic'].append(logisticcost)
            self.__arrayDict[ComponentType]['UnCoMaCostOM'].append(omcost)

        # Save the information about failure and down time in devices
        downtimeDeviceList = []
        keys = self.__arrayDict.keys()
        breakdown = self.__arrayDict[ComponentID]['Breakdown']

        for iCnt1 in range(0,len(keys)):

            if not ('device' in keys[iCnt1] and
                    self.__arrayDict[keys[iCnt1]]['UnCoMaNoWeatherWindow'] and
                    ('All' in breakdown or keys[iCnt1] in breakdown)):

                continue

            if self.__ignoreWeatherWindow:
                self.__arrayDict[keys[iCnt1]]['UnCoMaNoWeatherWindow'] = True
                self.__NrOfTurnOutDevices = self.__NrOfTurnOutDevices + 1

            downtimeDeviceList.append(str(keys[iCnt1]))

            # Save the information about failure
            self.__arrayDict[keys[iCnt1]][
                    'UnCoMaOpEvents'].append(failureDate)
            self.__arrayDict[keys[iCnt1]][
                    'UnCoMaOpEventsDuration'].append(totalDownTimeHours)
            self.__arrayDict[keys[iCnt1]][
                    'UnCoMaOpEventsIndexFM'].append(indexFM)
            self.__arrayDict[keys[iCnt1]][
                    'UnCoMaOpEventsCausedBy'].append(str(ComponentID))

            if 'device' in ComponentType: continue

            self.__arrayDict[keys[iCnt1]]['UnCoMaCostLogistic'].append(0.0)
            self.__arrayDict[keys[iCnt1]]['UnCoMaCostOM'].append(0.0)
            self.__arrayDict[ComponentID]['UnCoMaNoWeatherWindow'] = True

        # loopValuesForOutput
        loopValuesForOutput_UnCoMa = loopValuesForOutput_UnCoMa + 1

        # Update poisson events in eventTables
        self.__updatePoissonEvents()

        # for environmental team
        self.__env_assess(loop,
                          failureDate,
                          FM_ID, RA_ID,
                          optimal['schedule sea time'],
                          'UnCoMa')

        vessel_equip = self.__om_logistic['optimal']['vessel_equipment']

        valuesForOutput = [failureRate,
                           str(failureEvents.replace(second=0)),
                           str(repairActionEvents.replace(second=0)),
                           str(self.__departOpDate.replace(second=0)),
                           int(totalDownTimeHours),
                           self.__totalSeaTimeHour,
                           totalWaitingTimeHours,
                           '',
                           ComponentType,
                           ComponentSubType,
                           ComponentID,
                           FM_ID,
                           RA_ID,
                           indexFM,
                           int(optLogisticCostValue),
                           int(omCostValue-omCostValueSpare),
                           int(omCostValueSpare),
                           vessel_equip[0][0],
                           vessel_equip[0][1]]

        self.__UnCoMa_outputEventsTable.ix[loopValuesForOutput_UnCoMa] = \
                                                            valuesForOutput
        self.__UnCoMa_outputEventsTable.loc[loopValuesForOutput_UnCoMa,
                                            'downtimeDeviceList [-]'] = \
                                                            downtimeDeviceList

        # loop
        loop = loop + 1

        # time consumption UnCoMa
        stop_time_UnCoMa = timeit.default_timer()

        if self.__dtocean_maintenance_PRINT_FLAG == True:

            time = (stop_time_UnCoMa - start_time_UnCoMa) - \
                                (stop_time_logistic - start_time_logistic)
            print 'calcUnCoMa: Simulation Duration [s]: ' + str(time)

        return (loop,
                loopValuesForOutput_UnCoMa,
                flagCalcCoBaMa,
                flagCalcUnCoMa)

    def __calcLogistic(self):

        '''__calcLogistic function: calls of dtocean-logistics and saves the
        results

        '''

        self.__om_logistic = om_logistics_main(
                                           copy.deepcopy(self.__vessels),
                                           copy.deepcopy(self.__equipments),
                                           copy.deepcopy(self.__ports),
                                           self.__schedule_OLC,
                                           self.__other_rates,
                                           copy.deepcopy(self.__port_sf),
                                           copy.deepcopy(self.__vessel_sf),
                                           copy.deepcopy(self.__eq_sf),
                                           self.__site,
                                           self.__metocean,
                                           self.__device,
                                           self.__sub_device,
                                           self.__entry_point,
                                           self.__layout,
                                           self.__collection_point,
                                           self.__dynamic_cable,
                                           self.__static_cable,
                                           self.__connectors,
                                           self.__wp6_outputsForLogistic,
                                           self.__dtocean_logistics_PRINT_FLAG)

        return

    def __calcCostOfOM(self, FM_ID, CompIDWithIndex):

        '''__calcCostOfOM function: calculation of the cost of O&M

        Args:
            FM_ID: id of the failure mode
            CompIDWithIndex: component id with index

        Returns:
            omCostValueSpare: cost of spare
            omCostValue: cost of spare and labor

        '''


        # summer
        self.__summerTime = False

        # winter
        self.__winterTime = False

          # repairActionDate is in summer time or winter time
        if self.__repairActionDate.month in [3, 4, 5, 6, 7, 8]:
            self.__summerTime = True

        else:
            self.__winterTime = True

        self.__totalWeekEndWorkingHour = 0
        self.__totalNotWeekEndWorkingHour = 0
        self.__totalNightWorkingHour = 0
        self.__totalDayWorkingHour = 0

        if  (self.__summerTime == True and
             self.__Farm_OM['workdays_summer'] <= 7):

            divMod = divmod(self.__totalSeaTimeHour / self.__dayHours,
                            self.__Farm_OM['workdays_summer'])

            self.__totalNotWeekEndWorkingHour = divMod[0] * self.__dayHours
            self.__totalWeekEndWorkingHour = self.__totalSeaTimeHour - \
                                            self.__totalNotWeekEndWorkingHour

        if  (self.__winterTime == True and
             self.__Farm_OM['workdays_winter'] <= 7):

            divMod = divmod(self.__totalSeaTimeHour / self.__dayHours,
                            self.__Farm_OM['workdays_winter'])

            self.__totalNotWeekEndWorkingHour = divMod[0] * self.__dayHours
            self.__totalWeekEndWorkingHour = self.__totalSeaTimeHour - \
                                            self.__totalNotWeekEndWorkingHour

        # calc of self.__totalDayWorkingHour and self.__totalNightWorkingHour
        opdt = datetime.datetime(self.__departOpDate.year,
                                 self.__departOpDate.month,
                                 self.__departOpDate.day)
        nightstart = self.__startDayWorkingHour + 12

        dummyDayWorkingDate = opdt + \
                                    timedelta(hours=self.__startDayWorkingHour)
        dummyNightWorkingDate = opdt + timedelta(hours=nightstart)

        dursecs = (self.__departOpDate - dummyDayWorkingDate).total_seconds()
        diffHour = dursecs // 3600

        if 0 <= diffHour and diffHour < 12:

            dursecs = (self.__endOpDate - dummyDayWorkingDate).total_seconds()
            workingHourRelToDiffHour = dursecs // 3600
            divMod = divmod(workingHourRelToDiffHour, self.__dayHours)

            self.__totalDayWorkingHour = divMod[0] * self.__dayHours / 2.0

            if divMod[1] <= 12:
                self.__totalDayWorkingHour = self.__totalDayWorkingHour + \
                                                                    divMod[1]
            else:
                self.__totalDayWorkingHour = self.__totalDayWorkingHour + \
                                                        self.__dayHours / 2.0

            self.__totalDayWorkingHour = self.__totalDayWorkingHour - diffHour
            self.__totalNightWorkingHour = self.__totalSeaTimeHour - \
                                                    self.__totalDayWorkingHour

        else:

            dursecs = (self.__endOpDate - dummyNightWorkingDate
                                                           ).total_seconds()
            workingHourRelToDiffHour = dursecs // 3600
            divMod = divmod(workingHourRelToDiffHour, self.__dayHours)

            self.__totalNightWorkingHour = divMod[0] * self.__dayHours / 2.0

            if divMod[1] <= 12:
                self.__totalNightWorkingHour = self.__totalNightWorkingHour + \
                                                                    divMod[1]
            else:
                self.__totalNightWorkingHour = self.__totalNightWorkingHour + \
                                                        self.__dayHours / 2.0

            self.__totalNightWorkingHour = self.__totalNightWorkingHour - \
                                                                    diffHour
            self.__totalDayWorkingHour = self.__totalSeaTimeHour - \
                                                self.__totalNightWorkingHour

        totalDummy = self.__totalWeekEndWorkingHour + \
                                        self.__totalNotWeekEndWorkingHour

        if totalDummy != 0:

            nightNotWeekend = self.__totalNightWorkingHour * \
                                self.__totalNotWeekEndWorkingHour / totalDummy
            nightWeekend = self.__totalNightWorkingHour * \
                                self.__totalWeekEndWorkingHour / totalDummy

            dayNotWeekend = self.__totalDayWorkingHour * \
                                self.__totalNotWeekEndWorkingHour / totalDummy
            dayWeekend = self.__totalDayWorkingHour * \
                                self.__totalWeekEndWorkingHour / totalDummy

        else:

            nightNotWeekend = 0.0
            nightWeekend = 0.0

            dayNotWeekend = 0.0
            dayWeekend = 0.0

        if 'Insp' in FM_ID:

            number_technicians = self.__Inspection[CompIDWithIndex][
                                                        'number_technicians']
            number_specialists = self.__Inspection[CompIDWithIndex][
                                                        'number_specialists']

        else:

            number_technicians = self.__Repair_Action[CompIDWithIndex][
                                                        'number_technicians']
            number_specialists = self.__Repair_Action[CompIDWithIndex][
                                                        'number_specialists']

        wage_specialist_day = self.__Farm_OM['wage_specialist_day']
        wage_specialist_night = self.__Farm_OM['wage_specialist_night']
        wage_technician_day = self.__Farm_OM['wage_technician_day']
        wage_technician_night = self.__Farm_OM['wage_technician_night']

        # cost of OM for the current action [unit]
        cost_spare = self.__Failure_Mode[CompIDWithIndex][
                                                        'cost_spare']
        cost_spare_transit = self.__Failure_Mode[CompIDWithIndex][
                                                        'cost_spare_transit']
        cost_spare_loading = self.__Failure_Mode[CompIDWithIndex][
                                                        'cost_spare_loading']

        # cost of spare
        omCostValueSpare = cost_spare + cost_spare_transit + cost_spare_loading
        omCostValue = omCostValueSpare

        # Assumption
        wage_specialist_weekend = wage_specialist_night
        wage_technician_weekend = wage_technician_night

        # cost of specialists
        day_wage = number_specialists * wage_specialist_day
        night_wage = number_specialists * wage_specialist_night
        we_wage = number_specialists * wage_specialist_weekend

        omCostValue += day_wage * dayNotWeekend
        omCostValue += we_wage * dayWeekend
        omCostValue += night_wage * nightNotWeekend
        omCostValue += we_wage * nightWeekend

        # cost of technicians
        day_wage = number_technicians * wage_technician_day
        night_wage = number_technicians * wage_technician_night
        we_wage = number_technicians * wage_technician_weekend

        omCostValue += day_wage * dayNotWeekend
        omCostValue += we_wage * dayWeekend
        omCostValue += night_wage * nightNotWeekend
        omCostValue += we_wage * nightWeekend

        return omCostValueSpare, omCostValue

    def __env_assess(self, loop,
                           failureDate,
                           FM_ID,
                           RA_ID,
                           optSeaTime,
                           maintenanceType):

        '''Collection of signals for enviroumental assessment

        '''

        # For environmental assessment
        dictEnvAssessDummy = {}
        dictEnvAssessDummy['typeOfvessels [-]'] = []
        dictEnvAssessDummy['nrOfvessels [-]'] = []
        dictEnvAssessDummy['timeStampActions [-]'] = failureDate
        dictEnvAssessDummy['FM_ID [-]'] = FM_ID
        dictEnvAssessDummy['RA_ID [-]'] = RA_ID
        dictEnvAssessDummy['duration [h]'] = optSeaTime

        optimal_ve = self.__om_logistic['optimal']['vessel_equipment']

        for iCnt1 in range(0, len(optimal_ve)):

            i_ve = optimal_ve[iCnt1]
            dictEnvAssessDummy['typeOfvessels [-]'].append(i_ve[0])
            dictEnvAssessDummy['nrOfvessels [-]'].append(i_ve[1])

        if maintenanceType == 'UnCoMa':
            self.__UnCoMa_dictEnvAssess[loop] = dictEnvAssessDummy

        if maintenanceType == 'CaBaMa':
            self.__CaBaMa_dictEnvAssess[loop] = dictEnvAssessDummy

        if maintenanceType == 'CoBaMa':
            self.__CoBaMa_dictEnvAssess[loop] = dictEnvAssessDummy

        return

    def __updatePoissonEvents(self):

        '''__updatePoissonEvents function: Updates the poisson events

        '''

        belongsTo        = self.__UnCoMa_eventsTable.belongsTo[0]
        ComponentID      = self.__UnCoMa_eventsTable.ComponentID[0]

        #array = self.__arrayDict
        #event = self.__UnCoMa_eventsTable

        if (belongsTo == 'Array' and
            'All' in self.__arrayDict[ComponentID]['Breakdown']):

            # shift of the rows of eventTables
            for iCnt in range(self.__actIdxOfUnCoMa + 1,
                              len(self.__UnCoMa_eventsTable)):

                shiftDate = self.__UnCoMa_eventsTable.failureEvents[iCnt] + \
                                    timedelta(hours=self.__totalSeaTimeHour)

                self.__UnCoMa_eventsTable.loc[iCnt,
                                              'failureEvents'] = shiftDate

                shiftDate = \
                    self.__UnCoMa_eventsTable.repairActionEvents[iCnt] + \
                                    timedelta(hours=self.__totalSeaTimeHour)

                self.__UnCoMa_eventsTable.loc[iCnt,
                                              'repairActionEvents'] = shiftDate

        else:

            # shift of the rows of eventTables
            for iCnt in range(self.__actIdxOfUnCoMa + 1,
                              len(self.__UnCoMa_eventsTable)):

                if not (self.__UnCoMa_eventsTable.loc[
                         iCnt, 'ComponentID'] == ComponentID and
                    self.__UnCoMa_eventsTable.loc[iCnt, 'belongsTo'] in
                                self.__arrayDict[ComponentID]['Breakdown']):

                    continue

                shiftDate = self.__UnCoMa_eventsTable.failureEvents[iCnt] + \
                                    timedelta(hours=self.__totalSeaTimeHour)

                self.__UnCoMa_eventsTable.loc[iCnt,
                                              'failureEvents'] = shiftDate

                shiftDate = \
                    self.__UnCoMa_eventsTable.repairActionEvents[iCnt] + \
                                    timedelta(hours=self.__totalSeaTimeHour)

                self.__UnCoMa_eventsTable.loc[iCnt,
                                              'repairActionEvents'] = shiftDate

        # sort of eventsTable
        self.__UnCoMa_eventsTable.sort(
                                    columns=self.__UnCoMa_eventsTableKeys[1],
                                    inplace=True)

        return

    def __postCalculation(self):

        '''__postCalculation function: some post calculations

        '''

        # Calculation of the
        # self.__outputsOfWP6['lcoeOfArray [Euro/KWh]']
        # self.__outputsOfWP6['annualEnergyOfDevices [Wh]']
        # self.__outputsOfWP6['annualDownTimeOfDevices [h]']
        # self.__outputsOfWP6['annualEnergyOfArray [Wh]']
        # self.__outputsOfWP6['annualCapexOfArray [Euro]']
        # self.__outputsOfWP6['annualOpexOfArray [Euro]']

        dummyOpexAll = 0
        dummyEnergyAll = 0
        dummyDownTime = 0

        keys = self.__arrayDict.keys()

        for iCnt in range(0, len(keys)):

            arraycomp = self.__arrayDict[keys[iCnt]]

            # calculation of Opex
            logic = ('Hydrodynamic' in keys[iCnt] or
                     'Pto' in keys[iCnt] or
                     'Control' in keys[iCnt] or
                     'Support structure' in keys[iCnt] or
                     'Mooring line' in keys[iCnt] or
                     'Foundation' in keys[iCnt] or
                     'Dynamic cable' in keys[iCnt] or
                     'Array elec sub-system' in keys[iCnt])

            # OPEX of the all components of array and all devices
            if not logic:

                # corrective_maintenance
                if self.__Farm_OM['corrective_maintenance'] == True:

                    x = len(arraycomp['UnCoMaCostOM'])

                    for iCnt1 in range(0, x):
                        dummyOpexAll = dummyOpexAll + \
                            arraycomp['UnCoMaCostOM'][iCnt1]

                    x = len(arraycomp['UnCoMaCostLogistic'])

                    for iCnt1 in range(0, x):
                        dummyOpexAll = dummyOpexAll + \
                            arraycomp['UnCoMaCostLogistic'][iCnt1]

                # condition_based_maintenance
                if self.__Farm_OM['condition_based_maintenance'] == True:

                    x = len(arraycomp['CoBaMaCostOM'])

                    for iCnt1 in range(0, x):
                        dummyOpexAll = dummyOpexAll + \
                            arraycomp['CoBaMaCostOM'][iCnt1]

                    x = len(arraycomp['CoBaMaCostLogistic'])

                    for iCnt1 in range(0, x):
                        dummyOpexAll = dummyOpexAll + \
                            arraycomp['CoBaMaCostLogistic'][iCnt1]

                # calendar_based_maintenance
                if self.__Farm_OM['calendar_based_maintenance'] == True:

                    x = len(arraycomp['CaBaMaCostOM'])

                    for iCnt1 in range(0, x):
                        dummyOpexAll = dummyOpexAll + \
                            arraycomp['CaBaMaCostOM'][iCnt1]

                    x = len(arraycomp['CaBaMaCostLogistic'])

                    for iCnt1 in range(0, x):
                        dummyOpexAll = dummyOpexAll + \
                            arraycomp['CaBaMaCostLogistic'][iCnt1]

            # calculation of downtime
            if 'device' in keys[iCnt]:

                dummyDownTime = 0

                # corrective_maintenance
                if self.__Farm_OM['corrective_maintenance'] == True:

                    x = len(arraycomp['UnCoMaOpEventsDuration'])

                    for iCnt1 in range(0, x):
                        dummyDownTime = dummyDownTime + \
                            arraycomp['UnCoMaOpEventsDuration'][iCnt1]

                # condition_based_maintenance
                if self.__Farm_OM['condition_based_maintenance'] == True:

                    x = len(arraycomp['CoBaMaOpEventsDuration'])

                    for iCnt1 in range(0, x):
                        dummyDownTime = dummyDownTime + \
                            arraycomp['CoBaMaOpEventsDuration'][iCnt1]

                # calendar_based_maintenance
                if self.__Farm_OM['calendar_based_maintenance'] == True:

                    x = len(arraycomp['CaBaMaOpEventsDuration'])

                    for iCnt1 in range(0, x):
                        dummyDownTime = dummyDownTime + \
                            arraycomp['CaBaMaOpEventsDuration'][iCnt1]

                self.__arrayDict[keys[iCnt]]['DownTime'] = dummyDownTime

                powerWP2 = float(arraycomp['AnnualEnergyWP2']) / \
                                        (self.__dayHours * self.__yearDays)

                deviceOperationTime = self.__operationTimeDay * \
                                            self.__dayHours - dummyDownTime
                # for missionTime [year]
                energyPerDevice = powerWP2 * deviceOperationTime

                if self.__operationTimeYear != 0:
                    deviceenergy = float(energyPerDevice) / \
                                                    self.__operationTimeYear
                else:
                    deviceenergy = 0.0

                self.__arrayDict[keys[iCnt]]['AnnualEnergyWP6'] = deviceenergy

                index = int(keys[iCnt].rsplit('device')[1]) - 1

                # list -> Annual energy of each devices [Wh]
                deviceenergy = round(deviceenergy, 0)
                self.__outputsOfWP6[
                        'annualEnergyOfDevices [Wh]'][index] = deviceenergy

                # list -> annualDownTimeOfDevices [h]
                if self.__operationTimeYear != 0:
                    downtime = float(dummyDownTime) / self.__operationTimeYear
                    downtime = round(downtime, 0)
                else:
                    downtime = 0.0

                self.__outputsOfWP6[
                            'annualDownTimeOfDevices [h]'][index] = downtime

                dummyEnergyAll = dummyEnergyAll + energyPerDevice

        # float -> Annual energy of array [Wh]
        if self.__operationTimeYear != 0:
            arrayenergy = float(dummyEnergyAll) / self.__operationTimeYear
        else:
            arrayenergy = 0.0

        # float -> Annual OPEX of array in case of condition based maintenance
        # strategy [Euro]
        if self.__operationTimeYear != 0:
            arrayopex = float(dummyOpexAll) / self.__operationTimeYear
        else:
            arrayopex = 0.0

        # float -> Annual CAPEX of array in case of condition based maintenance strategy [Euro]
        arraycapex = round(self.__outputsOfWP6['CapexOfArray [Euro]'], 1)

        # LCOE of array [Euro/kWh]
        if not np.isclose(arrayenergy, 0):
            arraylcoe = arrayopex / \
                    (self.__outputsOfWP6['annualEnergyOfArray [Wh]'] / 1000.0)
        else:
            arraylcoe = 0.0

        # Round the outcomes
        arrayenergy = round(arrayenergy, 0)
        arrayopex = round(arrayopex, 2)
        arraycapex = round(arraycapex, 2)
        arraylcoe = round(arraylcoe, 4)

        self.__outputsOfWP6['annualEnergyOfArray [Wh]'] = arrayenergy
        self.__outputsOfWP6['annualOpexOfArray [Euro]'] = arrayopex
        self.__outputsOfWP6['CapexOfArray [Euro]'] = arraycapex
        self.__outputsOfWP6['lcoeOfArray [Euro/KWh]'] = arraylcoe

        # Pandas series -> Signals for environmental assessment.
        if self.__Farm_OM['corrective_maintenance'] == True:
            self.__outputsOfWP6['env_assess [-]']['UnCoMa_eventsTable'] = \
                                        pd.Series(self.__UnCoMa_dictEnvAssess)

        if self.__Farm_OM['calendar_based_maintenance'] == True:
         self.__outputsOfWP6['env_assess [-]']['CaBaMa_eventsTable'] = \
                                         pd.Series(self.__CaBaMa_dictEnvAssess)

        if self.__Farm_OM['condition_based_maintenance'] == True:
            self.__outputsOfWP6['env_assess [-]']['CoBaMa_eventsTable'] = \
                                        pd.Series(self.__CoBaMa_dictEnvAssess)

        # for maintenance plans
        self.__outputsOfWP6['eventTables [-]'][
                'UnCoMa_eventsTable'] = self.__UnCoMa_outputEventsTable
        self.__outputsOfWP6['eventTables [-]'][
                'CoBaMa_eventsTable'] = self.__CoBaMa_outputEventsTable
        self.__outputsOfWP6['eventTables [-]'][
                'CaBaMa_eventsTable'] = self.__CaBaMa_outputEventsTable

        return