"""Callbacks of the feedback on the environmental conditions of a site (see `environmental_conditions`).

Triggered by the site location and by the button fetching the environmental data, not by changes to
the configuration:

- The status callback asks the data source of the model type whether the data of the site are
  available, or being fetched, and enables the button, flags the feedback as stale, and writes the
  ready store accordingly.
- The fetch callback, a background callback, fetches the data into the environment cache. Requests
  for data already being fetched, such as by a model run, wait for that fetch rather than repeating
  it (see `environment_cache.get_or_set`).
- The draw callback draws the items with their registered artists, once the data are ready and the
  Details holding them is open.
"""
import logging
logger = logging.getLogger(__name__)

from dataclasses import dataclass
import json
import time
from typing import Any, Sequence

from dash import ALL, Input, Output, State, html
from dash.exceptions import PreventUpdate

from newsegsmodelapp import registers
from newsegsmodelapp.components.feedback import environmental_conditions as ec
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.core.environment.environment_servers import EnvironmentDataUnavailableError
from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject

def _model_type(app_state: str | None) -> str:
    try:
        return json.loads(app_state).get('model_type', 'default') if app_state else 'default'
    except (TypeError, ValueError, AttributeError):
        return 'default'

def site_location(site_location: str | None) -> Location | None:
    """The location of a 'site-location' store value; None if it has none.

    Only checks that a latitude and longitude are set: whether they are a valid site is left to
    the map module (to be addressed in a separate issue).

    Args:
        site_location: Value of the 'site-location' store.

    Returns:
        The location.
    """
    try:
        coords = json.loads(site_location) # pyright: ignore[reportArgumentType]
        return Location(float(coords['lat']), float(coords['lon']))
    except (TypeError, ValueError, KeyError, AttributeError):
        return None

def location_key(location: Location) -> str:
    """Key of a location in the stores of the feedback: its latitude and longitude to 3 dp, as in
    the environment cache."""
    return f'{location.lat:.3f},{location.lon:.3f}'

def location_from_key(key: str) -> Location:
    """The location of a key from `location_key`."""
    lat, lon = key.split(',')
    return Location(float(lat), float(lon))

def ready_key(location: Location, metamodel: NewsegsMetaModel) -> str:
    """Value of the ready store: the site and the metamodel whose feedback can be drawn. The data
    of a site depend on the metamodel, such as on the heights of its generators."""
    return json.dumps({'site': location_key(location), 'metamodel_id': metamodel.id})

def focussed_metamodel(
    project_provider: NewsegsProjectProviderInterface,
    active_project_id: str | None,
) -> NewsegsMetaModel | None:
    """The focussed metamodel of a project, constructed so that a data source can find what a
    run of it uses; None if there is no project.

    Args:
        project_provider: Provider of projects.
        active_project_id: Id of the project.

    Returns:
        The metamodel.
    """
    if not active_project_id:
        return None
    try:
        lproj = project_provider.get_lightweight_project(active_project_id)
    except KeyError:
        return None
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]
    return project_provider.metamodel_provider.get_component(lmm.id) # pyright: ignore[reportAttributeAccessIssue]

@dataclass
class EnvironmentFeedbackStatus:
    """The state of the environmental data of a site, and how the feedback shows it.

    Attributes:
        status: One of `unset` (no site location), `available`, `pending` (being fetched),
            `failed` (the last fetch for the site failed) and `missing`.
        message: Text of the status badge; empty to hide it.
        colour: Colour of the status badge.
        can_fetch: Whether the button fetching the data is enabled.
        ready: Value of the ready store (see `ready_key`) if the data are available to draw,
            otherwise None.
    """
    status: str
    message: str
    colour: str
    can_fetch: bool
    ready: str | None = None

    @property
    def stale(self) -> bool:
        """Whether any feedback shown is not of the site."""
        return self.status != 'available'

def get_status(
    source: registers.EnvironmentDataSource,
    location: Location | None,
    metamodel: NewsegsMetaModel | None,
    fetch_result: dict | None = None,
    fetch_requested: bool = False,
) -> EnvironmentFeedbackStatus:
    """The state of the environmental data of a site.

    Args:
        source: The data source of the model type.
        location: Location of the site; None if it is not set.
        metamodel: The focussed metamodel; None if there is no project.
        fetch_result: Result of the last fetch: the `key` of its site and its `error`, if any.
        fetch_requested: Whether the fetch requested by the user is running.

    Returns:
        The status.
    """
    if location is None or metamodel is None:
        return EnvironmentFeedbackStatus('unset', 'Set a site location', 'secondary', False)
    key = location_key(location)
    if source.is_available(location, metamodel):
        return EnvironmentFeedbackStatus('available', '', 'success', False, ready_key(location, metamodel))
    if fetch_requested or source.is_pending(location, metamodel):
        return EnvironmentFeedbackStatus('pending', 'Fetching environmental data…', 'info', False)
    if fetch_result and fetch_result.get('key') == key and fetch_result.get('error'):
        return EnvironmentFeedbackStatus('failed', fetch_result['error'], 'danger', True)
    return EnvironmentFeedbackStatus('missing', 'Environmental data not yet fetched for this site', 'warning', True)

def fetch_environment_data(
    source: registers.EnvironmentDataSource,
    location: Location,
    metamodel: NewsegsMetaModel,
) -> dict:
    """Fetch the environmental data of a site, returning the result for the fetch result store.

    Args:
        source: The data source of the model type.
        location: Location of the site.
        metamodel: The focussed metamodel.

    Returns:
        The `key` of the site, and the `error` if the data could not be obtained.
    """
    t0 = time.perf_counter()
    result: dict[str, Any] = {'key': location_key(location), 'error': None}
    try:
        source.fetch(location, metamodel)
    except EnvironmentDataUnavailableError as e:
        logger.warning('Environmental data unavailable for %s: %s', location, e)
        result['error'] = str(e)
    except Exception: # pylint: disable=broad-except
        logger.exception('Failed to fetch environmental data for %s', location)
        result['error'] = 'The environmental data could not be fetched'
    logger.info('Environmental data fetched for %s in %.3fs', location, time.perf_counter() - t0)
    return result

def other_sites(lproj: LightweightNewsegsProject, location: Location) -> list[tuple[str, Location]]:
    """The names and locations of the configurations of a project at sites other than a location.

    Args:
        lproj: The project.
        location: Location of the site shown.

    Returns:
        The sites, one for each location, in the order of the configurations. A site is named by
        its site name, or by its configuration if it has the default site name.
    """
    keys = {location_key(location)}
    sites = []
    for lmm in lproj.metamodels:
        loc = getattr(lmm, 'location', None)
        if loc is None:
            continue
        key = location_key(loc)
        if key in keys:
            continue
        keys.add(key)
        # Named by the site, unless it has the default name, when by the configuration
        site_name = getattr(loc, 'name', None)
        if not site_name or site_name == Location._name: # pyright: ignore[reportPrivateUsage]
            site_name = lmm.name
        sites.append((site_name, Location(loc.lat, loc.lon)))
    return sites

def draw_items(
    item_ids: Sequence[dict],
    model_type: str,
    location: Location,
    sites: Sequence[tuple[str, Location]],
    metamodel: NewsegsMetaModel,
) -> list:
    """Draw the items of environmental feedback.

    An item without an artist is left empty; an item whose artist fails says so.

    Args:
        item_ids: Ids of the items.
        model_type: The model type.
        location: Location of the site.
        sites: Names and locations of the other sites of the project.
        metamodel: The focussed metamodel.

    Returns:
        The children of each item.
    """
    children = []
    for id_ in item_ids:
        try:
            artist = registers.get_environment_feedback_artist(id_['key'], model_type)
        except KeyError:
            logger.error('No environment feedback artist for key %s', id_['key'])
            children.append(None)
            continue
        try:
            children.append(artist(location, sites, metamodel))
        except Exception: # pylint: disable=broad-except
            logger.exception('Failed to draw environment feedback %s', id_['key'])
            children.append(html.Div('This feedback could not be drawn', className = 'text-danger small'))
    return children

def add_environment_feedback_callbacks(app: NewsegsDash):
    """Bind the callbacks of the environmental feedback.

    The fetch callback is a background callback, so the app needs a background callback manager.

    Args:
        app: The Dash app.
    """
    @app.callback(
        Output(ec.FETCH_BUTTON_ID, 'disabled'),
        Output(ec.STATUS_ID, 'children'),
        Output(ec.STATUS_ID, 'color'),
        Output(ec.STATUS_ID, 'style'),
        Output(ec.CONTAINER_ID, 'className'),
        Output(ec.PENDING_INTERVAL_ID, 'disabled'),
        Output(ec.READY_ID, 'data'),

        Input('site-location', 'data'),
        Input(ec.FETCH_RESULT_ID, 'data'),
        Input(ec.PENDING_INTERVAL_ID, 'n_intervals'),
        Input(ec.FETCH_RUNNING_ID, 'data'),
        Input('active-project-id', 'data'),
        State('app-state', 'data'),
    )
    def update_environment_feedback_status(site_loc, fetch_result, n_intervals, fetch_running, active_project_id, app_state):
        source = registers.get_environment_data_source(_model_type(app_state))
        if source is None:
            raise PreventUpdate
        logger.debug('Getting metamodel - Updating environmental feedback status')
        status = get_status(
            source,
            site_location(site_loc),
            focussed_metamodel(app.project_provider, active_project_id),
            json.loads(fetch_result) if fetch_result else None,
            fetch_requested = bool(fetch_running),
        )
        logger.debug('Environmental feedback status: %s', status.status)
        return (
            not status.can_fetch,
            status.message,
            status.colour,
            {'display': 'inline-block' if status.message else 'none'},
            'mt-3' + (f' {ec.STALE_CLASS}' if status.stale else ''),
            status.status != 'pending',
            status.ready,
        )

    @app.callback(
        Output(ec.FETCH_RESULT_ID, 'data'),

        Input(ec.FETCH_BUTTON_ID, 'n_clicks'),
        State('site-location', 'data'),
        State('active-project-id', 'data'),
        State('app-state', 'data'),

        background = True,
        running = [
            (Output(ec.FETCH_SPINNER_ID, 'style'), {'display': 'inline-block'}, {'display': 'none'}),
            (Output(ec.FETCH_RUNNING_ID, 'data'), True, False),
        ],
        prevent_initial_call = True,
    )
    def fetch_site_environment_data(n_clicks, site_loc, active_project_id, app_state):
        source = registers.get_environment_data_source(_model_type(app_state))
        location = site_location(site_loc)
        if not n_clicks or source is None or location is None:
            raise PreventUpdate
        metamodel = focussed_metamodel(app.project_provider, active_project_id)
        if metamodel is None:
            raise PreventUpdate
        return json.dumps(fetch_environment_data(source, location, metamodel))

    @app.callback(
        Output({'type': ec.ITEM_TYPE, 'key': ALL}, 'children'),
        Output(ec.DRAWN_ID, 'data'),

        Input(ec.READY_ID, 'data'),
        Input(ec.SUMMARY_ID, 'n_clicks'),
        State(ec.DRAWN_ID, 'data'),
        State({'type': ec.ITEM_TYPE, 'key': ALL}, 'id'),
        State('active-project-id', 'data'),
        State('app-state', 'data'),
        prevent_initial_call = True,
    )
    def draw_environment_feedback(ready, summary_clicks, drawn, item_ids, active_project_id, app_state):
        # Nothing is drawn while the Details is closed (an even count of clicks on its Summary),
        # or for a site whose data are not ready; the feedback of the previous site stays,
        # flagged as stale
        details_open = bool(summary_clicks) and summary_clicks % 2 == 1
        if not details_open or not ready or ready == drawn or not item_ids:
            raise PreventUpdate
        t0 = time.perf_counter()
        location = location_from_key(json.loads(ready)['site'])
        logger.debug('Getting metamodel - Drawing environmental feedback')
        metamodel = focussed_metamodel(app.project_provider, active_project_id)
        if metamodel is None:
            raise PreventUpdate
        lproj = app.project_provider.get_lightweight_project(active_project_id)
        sites = other_sites(lproj, location)
        children = draw_items(item_ids, _model_type(app_state), location, sites, metamodel)
        logger.info('Environmental feedback drawn in %.3fs', time.perf_counter() - t0)
        return children, ready
