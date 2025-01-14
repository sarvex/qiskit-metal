#
from ast import parse
from qiskit_metal.renderers.renderer_ansys_pyaedt.hfss_renderer_aedt import QHFSSPyaedt
from qiskit_metal import Dict
from typing import List, Tuple, Union
import pandas as pd


class QHFSSEigenmodePyaedt(QHFSSPyaedt):
    """Subclass of pyaedt HFSS renderer for methods unique to driven-modal solutions within HFSS.
     QPyaedt Default Options:

    """
    name = 'aedt_hfss_eigenmode'

    default_setup = Dict(
        name="QHFSSEigenmodePyaedt_setup",
        MinimumFrequency="5.0",  # GHz
        NumModes="1",
        MaxDeltaFreq="0.5",
        MaximumPasses="10",
        MinimumPasses="1",
        MinimumConvergedPasses="1",
        PercentRefinement="30",
        BasisOrder="1")
    """aedt HFSS Options"""
    aedt_hfss_drivenmodal_options = Dict()

    def __init__(self,
                 multilayer_design: 'MultiPlanar',
                 project_name: Union[str, None] = None,
                 design_name: Union[str, None] = None,
                 initiate=False,
                 options: Dict = None):
        """Create a QRenderer for HFSS simulations using pyaedt and multiplanar design.
        QHFSSPyaedt is subclassed from QPyaedt, subclassed from QRendererAnalysis and
        subclassed from QRenderer.  The default_setup options are expected to be defined by
        child class of QHFSSPyaedt for driven-modal and eigenmode solution types.


        Args:

            multilayer_design (MultiPlanar): Use QGeometry within MultiPlanar to obtain elements for Ansys.
            project_name (Union[str, None], optional): Give a name, or one will be made based on class name of renderer.
                                            Defaults to None.
            design_name (Union[str, None], optional): Give a name, or one will be made based on class name of renderer.
                                            Defaults to None.
            initiate (bool, optional): True to initiate the renderer. Defaults to False.
            options (Dict, optional):  Used to override all options. Defaults to None.
        """

        super().__init__(multilayer_design,
                         renderer_type='HFSS_EM',
                         project_name=project_name,
                         design_name=design_name,
                         initiate=initiate,
                         options=options)

        #make a class to read in pandas table.
        self.tables = None

    def add_hfss_em_setup(
            self,
            name: str = None,
            MinimumFrequency: float = None,  # GHz
            NumModes: int = None,
            MaxDeltaFreq: float = None,
            MaximumPasses: int = None,
            MinimumPasses: int = None,
            MinimumConvergedPasses: int = None,
            PercentRefinement: int = None,
            BasisOrder: int = None):
        """Create a solution setup in Ansys HFSS Driven-Modal solution type. If user does not provide
        arguments, they will be obtained from QHFSSDrivenmodalPyaedt.default_setup dict.

        Args:
            name (str, optional): _description_. Defaults to None.
            MinimumFrequency (float, optional):  Minimum frequency in GHz. Defaults to self.default_setup.
            NumModes (int, optional): Number of modes.  Defaults to self.default_setup.
            MaxDeltaFreq (float, optional):   Maximum difference in freq between consecutive passes.
                                        Defaults to self.default_setup.
            MaximumPasses (int, optional):  Maximum number of passes. Defaults to self.default_setup.
            MinimumPasses (int, optional): Minimum number of passes.Defaults to self.default_setup.
            MinimumConvergedPasses (int, optional): Minimum number of converged passes.
                                        Defaults to self.default_setup.
            PercentRefinement (int, optional): Percent refinement. Defaults to self.default_setup.
            BasisOrder (int, optional): Basis order. Defaults to self.default_setup.

        """

        self.activate_user_project_design()

        esu = self.default_setup

        if not name:
            name = self.parse_value(esu['name'])

        if name in self.current_app.setup_names:
            self.logger.warning(
                f'The setup name already exists within '
                f'project:{self.project_name} design: {self.design_name}. '
                f'So a new setup with name={name} was NOT added to design.')
            return

        if not MinimumFrequency:
            MinimumFrequency = float(self.parse_value(esu['MinimumFrequency']))
        if not NumModes:
            NumModes = int(self.parse_value(esu['NumModes']))
        if not MaxDeltaFreq:
            MaxDeltaFreq = float(self.parse_value(esu['MaxDeltaFreq']))
        if not MaximumPasses:
            MaximumPasses = int(self.parse_value(esu['MaximumPasses']))
        if not MinimumPasses:
            MinimumPasses = int(self.parse_value(esu['MinimumPasses']))
        if not MinimumConvergedPasses:
            MinimumConvergedPasses = int(
                self.parse_value(esu['MinimumConvergedPasses']))
        if not PercentRefinement:
            PercentRefinement = int(self.parse_value(esu['PercentRefinement']))
        if not BasisOrder:
            BasisOrder = int(self.parse_value(esu['BasisOrder']))

        new_setup = self.current_app.create_setup(name)

        new_setup.props['MinimumFrequency'] = f'{MinimumFrequency}GHz'
        new_setup.props['NumModes'] = NumModes
        new_setup.props['MaxDeltaFreq'] = MaxDeltaFreq
        new_setup.props['MaximumPasses'] = MaximumPasses
        new_setup.props['MinimumPasses'] = MinimumPasses
        new_setup.props['MinimumConvergedPasses'] = MinimumConvergedPasses
        new_setup.props['PercentRefinement'] = PercentRefinement
        new_setup.props['BasisOrder'] = BasisOrder

        new_setup.update()

    def render_design(self,
                      selection: Union[list, None] = None,
                      open_pins: Union[list, None] = None,
                      port_list: Union[list, None] = None,
                      jj_to_port: Union[list, None] = None,
                      ignored_jjs: Union[list, None] = None,
                      box_plus_buffer: bool = True):
        """
        This render_design will add additional logic for just eigenmode design within project.

        Initiate rendering of components in design contained in selection,
        assuming they're valid. Components are rendered before the chips they
        reside on, and subtraction of negative shapes is performed at the very
        end.

        First obtain a list of IDs of components to render and a corresponding case, denoted by self.qcomp_ids
        and self.case, respectively. If self.case == 1, all components in QDesign are to be rendered.
        If self.case == 0, a strict subset of components in QDesign are to be rendered. Otherwise, if
        self.case == 2, one or more component names in selection cannot be found in QDesign.

        Chip_subtract_dict consists of component names (keys) and a set of all elements within each component that
        will eventually be subtracted from the ground plane. Add objects that are perfect conductors and/or have
        meshing to self.assign_perfE and self.assign_mesh, respectively; both are initialized as empty lists. Note
        that these objects are "refreshed" each time render_design is called (as opposed to in the init function)
        to clear QAnsysRenderer of any leftover items from the last call to render_design.

        Among the components selected for export, there may or may not be unused (unconnected) pins.
        The second parameter, open_pins, contains tuples of the form (component_name, pin_name) that
        specify exactly which pins should be open rather than shorted during the simulation. Both the
        component and pin name must be specified because the latter could be shared by multiple
        components. All pins in this list are rendered with an additional endcap in the form of a
        rectangular cutout, to be subtracted from its respective plane.

        The final parameter, box_plus_buffer, determines how the chip is drawn. When set to True, it takes the
        minimum rectangular bounding box of all rendered components and adds a buffer of x_buffer_width_mm and
        y_buffer_width_mm horizontally and vertically, respectively, to the chip size. The center of the chip
        lies at the midpoint x/y coordinates of the minimum rectangular bounding box and may change depending
        on which components are rendered and how they're positioned. If box generated with box_plus_buffer
        passes the chip size, the box will be cropped to chip size. If box_plus_buffer is False, however, the
        chip position and dimensions are taken from the chip info dictionary found in self.design, irrespective
        of what's being rendered. While this latter option is faster because it doesn't require calculating a
        bounding box, it runs the risk of rendered components being too close to the edge of the chip or even
        falling outside its boundaries.

        Args:
            selection (Union[list, None], optional): List of components to render. Defaults to None.
            open_pins (Union[list, None], optional): List of tuples of pins that are open. Defaults to None.
            box_plus_buffer (bool, optional): Either calculate a bounding box based on the location of rendered geometries
                                     or use chip size from design class.
        """
        # self.fill_info will hold the name of newly generated box,
        # along with information from layer stack
        self.fill_info = self.design.ls.get_layer_datatype_when_fill_is_true()

        # Draw in fill = True pieces. based on either full chip or box_plus

        # They are reset for each time render_design happens.

        # jj_to_port SHOULD not bew in eigenmode solution type. So will give error
        if jj_to_port or port_list:
            self.design.logger.error(
                f'In eigenmode solution, there should NOT be any values for jj_to_port or port_list.'
            )
            return

        super().render_design(selection, open_pins, port_list, jj_to_port,
                              ignored_jjs, box_plus_buffer)

        if self.case == 2:
            self.logger.warning(
                'Unable to proceed with rendering. Please check selection.')
            return

        self.activate_user_project_design()

        # Ansys default units is 'mm'?????, but metal using 'meter'.
        # pyaedt.generic.constants.SI_UNITS.Length is meter.

        # self.add_mesh()
        # self.assign_thin_conductor()
        # self.assign_nets()

        self.add_mesh()

        return

    def add_mesh(self):
        a = 5

    def should_render_junction(self, qgeom: pd.Series, port_list: Union[list,
                                                                        None],
                               jj_to_port: Union[list, None],
                               ignored_jjs: Union[list, None]) -> bool:
        """Logic Just for eigenmode

        Args:
            qgeom (pd.Series): One row of the junction table.
            port_list (Union[list, None]): Use definition from render_design.
            jj_to_port (Union[list, None]): Use definition from render_design.
            ignored_jjs (Union[list, None]): Use definition from render_design.

        Returns:
            bool: If the junction should be rendered based on row from junction
                table and ignored_jjs.
        """

        if ignored_jjs:
            search_junction = (self.design._components[qgeom["component"]].name,
                               qgeom['name'])
            if search_junction in ignored_jjs:
                return False

        return True
