"""
Main API functions for the user to start and stop analytics tracking.
"""

import datetime
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional, Union

import streamlit as st
from streamlit import session_state as ss

from . import display, firestore, utils, widgets  # noqa: F811 F401
from . import wrappers as _wrap
from .state import data, reset_data

# from streamlit_searchbox import st_searchbox

# TODO look into https://github.com/444B/streamlit-analytics2/pull/119 to
# integrate
# logging.basicConfig(
#     level=logging.INFO,
#     format="streamlit-analytics2: %(levelname)s: %(message)s"
# )
# Uncomment this during testing
# logging.info("SA2: Streamlit-analytics2 successfully imported")


_PERSISTENCE_RECORD_TYPE_KEY = "__streamlit_analytics_record_type__"
_PERSISTENCE_RECORD_TYPE_SESSION = "session_snapshot"
_SESSION_PERSISTENCE_FLAG = "_sa2_usage_snapshot_persisted"


def _empty_analytics_snapshot() -> Dict[str, Any]:
    yesterday = str(datetime.date.today() - datetime.timedelta(days=1))
    return {
        "loaded_from_firestore": False,
        "total_pageviews": 0,
        "total_script_runs": 0,
        "total_time_seconds": 0,
        "per_day": {
            "days": [yesterday],
            "pageviews": [0],
            "script_runs": [0],
        },
        "widgets": {},
        "start_time": datetime.datetime.now().strftime("%d %b %Y, %H:%M:%S"),
    }


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_start_time(value: Any) -> datetime.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.datetime.strptime(value, "%d %b %Y, %H:%M:%S")
    except ValueError:
        return None


def _merge_daily_counts(target: Dict[str, list[Any]], source: Dict[str, Any]) -> None:
    source_days = [str(day) for day in source.get("days", [])]
    source_pageviews = list(source.get("pageviews", []))
    source_script_runs = list(source.get("script_runs", []))

    target_days = target.setdefault("days", [])
    target_pageviews = target.setdefault("pageviews", [])
    target_script_runs = target.setdefault("script_runs", [])
    day_to_index = {str(day): idx for idx, day in enumerate(target_days)}

    for idx, day in enumerate(source_days):
        pageviews = _coerce_int(source_pageviews[idx] if idx < len(source_pageviews) else 0)
        script_runs = _coerce_int(source_script_runs[idx] if idx < len(source_script_runs) else 0)
        if day in day_to_index:
            target_idx = day_to_index[day]
            target_pageviews[target_idx] = _coerce_int(target_pageviews[target_idx]) + pageviews
            target_script_runs[target_idx] = _coerce_int(target_script_runs[target_idx]) + script_runs
        else:
            day_to_index[day] = len(target_days)
            target_days.append(day)
            target_pageviews.append(pageviews)
            target_script_runs.append(script_runs)


def _merge_widget_counts(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    for widget_name, widget_value in source.items():
        if isinstance(widget_value, dict):
            target_widget = target.get(widget_name)
            if not isinstance(target_widget, dict):
                target_widget = {}
                target[widget_name] = target_widget
            for selected_value, count in widget_value.items():
                selected_key = str(selected_value)
                target_widget[selected_key] = _coerce_int(target_widget.get(selected_key, 0)) + _coerce_int(count)
        else:
            target[widget_name] = _coerce_int(target.get(widget_name, 0)) + _coerce_int(widget_value)


def _merge_analytics_snapshots(*snapshots: Dict[str, Any]) -> Dict[str, Any]:
    merged = _empty_analytics_snapshot()
    earliest_start = _parse_start_time(merged.get("start_time"))

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue

        merged["total_pageviews"] += _coerce_int(snapshot.get("total_pageviews"))
        merged["total_script_runs"] += _coerce_int(snapshot.get("total_script_runs"))
        merged["total_time_seconds"] += float(snapshot.get("total_time_seconds", 0) or 0)

        per_day = snapshot.get("per_day")
        if isinstance(per_day, dict):
            _merge_daily_counts(merged["per_day"], per_day)

        widgets = snapshot.get("widgets")
        if isinstance(widgets, dict):
            _merge_widget_counts(merged["widgets"], widgets)

        start_time = _parse_start_time(snapshot.get("start_time"))
        if start_time is not None and (earliest_start is None or start_time < earliest_start):
            earliest_start = start_time

    if earliest_start is not None:
        merged["start_time"] = earliest_start.strftime("%d %b %Y, %H:%M:%S")
    return merged


def _load_persisted_analytics_snapshot(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None

    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return None

    try:
        loaded = json.loads(raw_text)
    except json.JSONDecodeError:
        records: list[Dict[str, Any]] = []
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        if not records:
            return None

        snapshots: list[Dict[str, Any]] = []
        for idx, record in enumerate(records):
            if record.get(_PERSISTENCE_RECORD_TYPE_KEY) == _PERSISTENCE_RECORD_TYPE_SESSION:
                snapshot = record.get("data")
                if isinstance(snapshot, dict):
                    snapshots.append(snapshot)
            elif idx == 0:
                snapshots.append(record)
            else:
                snapshots.append(record)
        return _merge_analytics_snapshots(*snapshots)

    if isinstance(loaded, dict):
        if loaded.get(_PERSISTENCE_RECORD_TYPE_KEY) == _PERSISTENCE_RECORD_TYPE_SESSION:
            session_snapshot = loaded.get("data")
            if isinstance(session_snapshot, dict):
                return _merge_analytics_snapshots(session_snapshot)
            return None
        return _merge_analytics_snapshots(loaded)

    if isinstance(loaded, list):
        snapshots = [item for item in loaded if isinstance(item, dict)]
        if not snapshots:
            return None
        return _merge_analytics_snapshots(*snapshots)

    return None


def _append_session_snapshot(path: Path, session_snapshot: Dict[str, Any]) -> None:
    record = {
        _PERSISTENCE_RECORD_TYPE_KEY: _PERSISTENCE_RECORD_TYPE_SESSION,
        "recorded_at": datetime.datetime.now().isoformat(),
        "data": session_snapshot,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        file_handle.write("\n")


def _persist_analytics_snapshot(path: Path, snapshot: Dict[str, Any]) -> None:
    _append_session_snapshot(path, snapshot)


def update_session_stats(data_dict: Dict[str, Any]):
    """
    Update the session data with the current state.

    Parameters
    ----------
    data : Dict[str, Any]
        Data, either aggregate or session-specific.

    Returns
    -------
    Dict[str, Any]
        Updated data with the current state of time-dependent elements.
    """
    today = str(datetime.date.today())
    if data_dict["per_day"]["days"][-1] != today:
        # TODO: Insert 0 for all days between today and last entry.
        data_dict["per_day"]["days"].append(today)
        data_dict["per_day"]["pageviews"].append(0)
        data_dict["per_day"]["script_runs"].append(0)
    data_dict["total_script_runs"] += 1
    data_dict["per_day"]["script_runs"][-1] += 1
    now = datetime.datetime.now()
    data_dict["total_time_seconds"] += (
        now - st.session_state.last_time
    ).total_seconds()
    st.session_state.last_time = now
    # Track not including refresh
    if not st.session_state.user_tracked:
        st.session_state.user_tracked = True
        data_dict["total_pageviews"] += 1
        data_dict["per_day"]["pageviews"][-1] += 1
    # Count each script pass as a pageview so browser refreshes are reflected.
    # data_dict["total_pageviews"] += 1
    # data_dict["per_day"]["pageviews"][-1] += 1
    # st.session_state.user_tracked = True


def _track_user():
    """Track individual pageviews by storing user id to session state."""
    update_session_stats(data)
    update_session_stats(ss.session_data)


def start_tracking(
    unsafe_password: Optional[str] = None,
    save_to_json: Optional[Union[str, Path]] = None,
    load_from_json: Optional[Union[str, Path]] = None,
    firestore_project_name: Optional[str] = None,
    firestore_collection_name: Optional[str] = None,
    firestore_document_name: Optional[str] = "counts",
    firestore_key_file: Optional[str] = None,
    streamlit_secrets_firestore_key: Optional[str] = None,
    session_id: Optional[str] = None,
    verbose=False,
):
    """
    Start tracking user inputs to a streamlit app.

    If you call this function directly, you NEED to call `streamlit_analytics.
    stop_tracking()` at the end of your streamlit script. For a more convenient
    interface, wrap your streamlit calls in `with streamlit_analytics.track():`.
    """
    utils.initialize_session_data()

    if (
        streamlit_secrets_firestore_key is not None
        and not data["loaded_from_firestore"]
    ):
        # Load both global and session data in a single call
        firestore.load(
            data=data,
            service_account_json=None,
            collection_name=firestore_collection_name,
            document_name=firestore_document_name,
            streamlit_secrets_firestore_key=streamlit_secrets_firestore_key,
            firestore_project_name=firestore_project_name,
            session_id=session_id,  # This will load global and session data
        )
        data["loaded_from_firestore"] = True
        if verbose:
            print("Loaded count data from firestore:")
            print(data)
            if session_id:
                print("Loaded session count data from firestore:")
                print(ss.session_data)
            print()

    elif firestore_key_file and not data["loaded_from_firestore"]:
        firestore.load(
            data,
            firestore_key_file,
            firestore_collection_name,
            firestore_document_name,
            streamlit_secrets_firestore_key=None,
            firestore_project_name=None,
            session_id=session_id,
        )
        data["loaded_from_firestore"] = True
        if verbose:
            print("Loaded count data from firestore:")
            print(data)
            print()

    if load_from_json is not None:
        # The txt-backed store is a cumulative snapshot, so refreshes/reopens
        # can be reflected immediately by rewriting it after tracking starts.
        log_msg_prefix = "Loading data from json: "
        try:
            snapshot = _load_persisted_analytics_snapshot(Path(load_from_json))
            if snapshot is not None:
                data.update(snapshot)

            if verbose:
                logging.info(f"{log_msg_prefix}{load_from_json}")
                logging.info("SA2: Success! Loaded data:")
                logging.info(data)

        except FileNotFoundError:
            if verbose:
                logging.warning(f"SA2: File {load_from_json} not found")
                logging.warning("Proceeding with empty data.")

        except Exception as e:
            # Catch-all for any other exceptions, log the error
            logging.error(f"SA2: Error loading data from {load_from_json}: {e}")

    # Reset session state.
    if "user_tracked" not in st.session_state:
        st.session_state.user_tracked = False
    if "state_dict" not in st.session_state:
        st.session_state.state_dict = {}
    if "last_time" not in st.session_state:
        st.session_state.last_time = datetime.datetime.now()
    if _SESSION_PERSISTENCE_FLAG not in st.session_state:
        st.session_state[_SESSION_PERSISTENCE_FLAG] = False
    _track_user()

    # Persist the per-session snapshot immediately so a new browser/session is
    # captured as soon as the run starts, while still appending only once.
    if load_from_json is not None and not st.session_state[_SESSION_PERSISTENCE_FLAG]:
        _persist_analytics_snapshot(Path(load_from_json), ss.session_data)
        st.session_state[_SESSION_PERSISTENCE_FLAG] = True

    # widgets.monkey_patch()
    # Monkey-patch streamlit to call the wrappers above.
    st.button = _wrap.button(_orig_button)
    st.checkbox = _wrap.checkbox(_orig_checkbox)
    st.radio = _wrap.select(_orig_radio)
    st.selectbox = _wrap.select(_orig_selectbox)
    st.multiselect = _wrap.multiselect(_orig_multiselect)
    st.slider = _wrap.value(_orig_slider)
    st.select_slider = _wrap.select(_orig_select_slider)
    st.text_input = _wrap.value(_orig_text_input)
    st.number_input = _wrap.value(_orig_number_input)
    st.text_area = _wrap.value(_orig_text_area)
    st.date_input = _wrap.value(_orig_date_input)
    st.time_input = _wrap.value(_orig_time_input)
    st.file_uploader = _wrap.file_uploader(_orig_file_uploader)
    st.color_picker = _wrap.value(_orig_color_picker)
    # new elements, testing
    # st.download_button = _wrap.value(_orig_download_button)
    # st.link_button = _wrap.value(_orig_link_button)
    # st.page_link = _wrap.value(_orig_page_link)
    # st.toggle = _wrap.value(_orig_toggle)
    # st.camera_input = _wrap.value(_orig_camera_input)
    st.chat_input = _wrap.chat_input(_orig_chat_input)
    # st_searchbox = _wrap.searchbox(_orig_searchbox)

    st.sidebar.button = _wrap.button(_orig_sidebar_button)  # type: ignore
    st.sidebar.radio = _wrap.select(_orig_sidebar_radio)  # type: ignore
    st.sidebar.selectbox = _wrap.select(_orig_sidebar_selectbox)  # type: ignore
    st.sidebar.multiselect = _wrap.multiselect(_orig_sidebar_multiselect)  # type: ignore
    st.sidebar.slider = _wrap.value(_orig_sidebar_slider)  # type: ignore
    st.sidebar.select_slider = _wrap.select(_orig_sidebar_select_slider)  # type: ignore
    st.sidebar.text_input = _wrap.value(_orig_sidebar_text_input)  # type: ignore
    st.sidebar.number_input = _wrap.value(_orig_sidebar_number_input)  # type: ignore
    st.sidebar.text_area = _wrap.value(_orig_sidebar_text_area)  # type: ignore
    st.sidebar.date_input = _wrap.value(_orig_sidebar_date_input)  # type: ignore
    st.sidebar.time_input = _wrap.value(_orig_sidebar_time_input)  # type: ignore
    st.sidebar.file_uploader = _wrap.file_uploader(_orig_sidebar_file_uploader)  # type: ignore
    st.sidebar.color_picker = _wrap.value(_orig_sidebar_color_picker)  # type: ignore
    # st.sidebar.st_searchbox = _wrap.searchbox(_orig_sidebar_searchbox)

    # new elements, testing
    # st.sidebar.download_button = _wrap.value(_orig_sidebar_download_button)
    # st.sidebar.link_button = _wrap.value(_orig_sidebar_link_button)
    # st.sidebar.page_link = _wrap.value(_orig_sidebar_page_link)
    # st.sidebar.toggle = _wrap.value(_orig_sidebar_toggle)
    # st.sidebar.camera_input = _wrap.value(_orig_sidebar_camera_input)

    # replacements = {
    #     "button": _wrap.bool,
    #     "checkbox": _wrap.bool,
    #     "radio": _wrap.select,
    #     "selectbox": _wrap.select,
    #     "multiselect": _wrap.multiselect,
    #     "slider": _wrap.value,
    #     "select_slider": _wrap.select,
    #     "text_input": _wrap.value,
    #     "number_input": _wrap.value,
    #     "text_area": _wrap.value,
    #     "date_input": _wrap.value,
    #     "time_input": _wrap.value,
    #     "file_uploader": _wrap.file_uploader,
    #     "color_picker": _wrap.value,
    # }

    if verbose:
        logging.info("\nSA2:  streamlit-analytics2 verbose logging")


def stop_tracking(
    unsafe_password: Optional[str] = None,
    save_to_json: Optional[Union[str, Path]] = None,
    load_from_json: Optional[Union[str, Path]] = None,
    firestore_project_name: Optional[str] = None,
    firestore_collection_name: Optional[str] = None,
    firestore_document_name: Optional[str] = "counts",
    firestore_key_file: Optional[str] = None,
    streamlit_secrets_firestore_key: Optional[str] = None,
    session_id: Optional[str] = None,
    verbose=False,
):
    """
    Stop tracking user inputs to a streamlit app.

    Should be called after `streamlit-analytics.start_tracking()`.
    This method also shows the analytics results below your app if you attach
    `?analytics=on` to the URL.
    """

    if verbose:
        logging.info("SA2: Finished script execution. New data:")
        logging.info(
            "%s", data
        )  # Use %s and pass data to logging to handle complex objects
        logging.info("%s", "-" * 80)  # For separators or multi-line messages

    # widgets.reset_widgets()

    # Reset streamlit functions.
    st.button = _orig_button
    st.checkbox = _orig_checkbox
    st.radio = _orig_radio
    st.selectbox = _orig_selectbox
    st.multiselect = _orig_multiselect
    st.slider = _orig_slider
    st.select_slider = _orig_select_slider
    st.text_input = _orig_text_input
    st.number_input = _orig_number_input
    st.text_area = _orig_text_area
    st.date_input = _orig_date_input
    st.time_input = _orig_time_input
    st.file_uploader = _orig_file_uploader
    st.color_picker = _orig_color_picker
    # new elements, testing
    # st.download_button = _orig_download_button
    # st.link_button = _orig_link_button
    # st.page_link = _orig_page_link
    # st.toggle = _orig_toggle
    # st.camera_input = _orig_camera_input
    st.chat_input = _orig_chat_input
    # st.searchbox = _orig_searchbox
    st.sidebar.button = _orig_sidebar_button  # type: ignore
    st.sidebar.checkbox = _orig_sidebar_checkbox  # type: ignore
    st.sidebar.radio = _orig_sidebar_radio  # type: ignore
    st.sidebar.selectbox = _orig_sidebar_selectbox  # type: ignore
    st.sidebar.multiselect = _orig_sidebar_multiselect  # type: ignore
    st.sidebar.slider = _orig_sidebar_slider  # type: ignore
    st.sidebar.select_slider = _orig_sidebar_select_slider  # type: ignore
    st.sidebar.text_input = _orig_sidebar_text_input  # type: ignore
    st.sidebar.number_input = _orig_sidebar_number_input  # type: ignore
    st.sidebar.text_area = _orig_sidebar_text_area  # type: ignore
    st.sidebar.date_input = _orig_sidebar_date_input  # type: ignore
    st.sidebar.time_input = _orig_sidebar_time_input  # type: ignore
    st.sidebar.file_uploader = _orig_sidebar_file_uploader  # type: ignore
    st.sidebar.color_picker = _orig_sidebar_color_picker  # type: ignore
    # new elements, testing
    # st.sidebar.download_button = _orig_sidebar_download_button
    # st.sidebar.link_button = _orig_sidebar_link_button
    # st.sidebar.page_link = _orig_sidebar_page_link
    # st.sidebar.toggle = _orig_sidebar_toggle
    # st.sidebar.camera_input = _orig_sidebar_camera_input
    # st.sidebar.searchbox = _orig_sidebar_searchbox
    # Save count data to firestore.
    # TODO: Maybe don't save on every iteration but on regular intervals in a
    # background thread.

    if (
        streamlit_secrets_firestore_key is not None
        and firestore_project_name is not None
    ):
        if verbose:
            print("Saving count data to firestore:")
            print(data)
            print("Saving session count data to firestore:")
            print(ss.session_data)
            print()

        # Save both global and session data in a single call
        firestore.save(
            data=data,
            service_account_json=None,
            collection_name=firestore_collection_name,
            document_name=firestore_document_name,
            streamlit_secrets_firestore_key=streamlit_secrets_firestore_key,
            firestore_project_name=firestore_project_name,
            session_id=session_id,  # This will save global and session data
        )

    elif (
        streamlit_secrets_firestore_key is None
        and firestore_project_name is None
        and firestore_key_file
    ):
        if verbose:
            print("Saving count data to firestore:")
            print(data)
            print()
        firestore.save(
            data,
            firestore_key_file,
            firestore_collection_name,
            firestore_document_name,
            streamlit_secrets_firestore_key=None,
            firestore_project_name=None,
            session_id=session_id,
        )

    # Dump the data to json file if `save_to_json` is set.
    # TODO: Make sure this is not locked if writing from multiple threads.

    # Assuming 'data' is your data to be saved and 'save_to_json' is the path
    # to your json file.
    if save_to_json is not None and not st.session_state.get(_SESSION_PERSISTENCE_FLAG, False):
        _persist_analytics_snapshot(Path(save_to_json), ss.session_data)
        st.session_state[_SESSION_PERSISTENCE_FLAG] = True

        if verbose:
            print("Storing results to file:", save_to_json)

    # Show analytics results in the streamlit app if `?analytics=on` is set in
    # the URL.
    query_params = st.query_params
    if "analytics" in query_params and "on" in query_params["analytics"]:

        @st.dialog("Streamlit-Analytics2", width="large")
        def show_sa2(data, reset_data, unsafe_password):

            display.show_results(data, reset_data, unsafe_password)

        show_sa2(data, reset_data, unsafe_password)


@contextmanager
def track(
    unsafe_password: Optional[str] = None,
    save_to_json: Optional[Union[str, Path]] = None,
    load_from_json: Optional[Union[str, Path]] = None,
    firestore_project_name: Optional[str] = None,
    firestore_collection_name: Optional[str] = None,
    firestore_document_name: Optional[str] = "counts",
    firestore_key_file: Optional[str] = None,
    streamlit_secrets_firestore_key: Optional[str] = None,
    session_id: Optional[str] = None,
    verbose=False,
):
    """
    Context manager to start and stop tracking user inputs to a streamlit app.

    To use this, make calls to streamlit in `with streamlit_analytics.track():`.
    This also shows the analytics results below your app if you attach
    `?analytics=on` to the URL.
    """
    if (
        streamlit_secrets_firestore_key is not None
        and firestore_project_name is not None
    ):
        start_tracking(
            firestore_collection_name=firestore_collection_name,
            firestore_document_name=firestore_document_name,
            streamlit_secrets_firestore_key=streamlit_secrets_firestore_key,
            firestore_project_name=firestore_project_name,
            session_id=session_id,
            verbose=verbose,
        )

    else:
        start_tracking(
            firestore_key_file=firestore_key_file,
            firestore_collection_name=firestore_collection_name,
            firestore_document_name=firestore_document_name,
            load_from_json=load_from_json,
            session_id=session_id,
            verbose=verbose,
        )
    # Yield here to execute the code in the with statement. This will call the
    # wrappers above, which track all inputs.
    yield
    if (
        streamlit_secrets_firestore_key is not None
        and firestore_project_name is not None
    ):
        stop_tracking(
            unsafe_password=unsafe_password,
            firestore_collection_name=firestore_collection_name,
            firestore_document_name=firestore_document_name,
            streamlit_secrets_firestore_key=streamlit_secrets_firestore_key,
            firestore_project_name=firestore_project_name,
            session_id=session_id,
            verbose=verbose,
        )
    else:
        stop_tracking(
            unsafe_password=unsafe_password,
            save_to_json=save_to_json,
            firestore_key_file=firestore_key_file,
            firestore_collection_name=firestore_collection_name,
            firestore_document_name=firestore_document_name,
            verbose=verbose,
            session_id=session_id,
        )


if __name__.endswith(".main"):
    reset_data()

    # widgets.copy_original()
    # TODO need to fix the scope for this function call and then we can move
    # these variable assignments to widgets.py

    # Store original streamlit functions. They will be monkey-patched with some
    # wrappers in `start_tracking` (see wrapper functions below).
    _orig_button = st.button
    _orig_checkbox = st.checkbox
    _orig_radio = st.radio
    _orig_selectbox = st.selectbox
    _orig_multiselect = st.multiselect
    _orig_slider = st.slider
    _orig_select_slider = st.select_slider
    _orig_text_input = st.text_input
    _orig_number_input = st.number_input
    _orig_text_area = st.text_area
    _orig_date_input = st.date_input
    _orig_time_input = st.time_input
    _orig_file_uploader = st.file_uploader
    _orig_color_picker = st.color_picker
    # new elements, testing
    # _orig_download_button = st.download_button
    # _orig_link_button = st.link_button
    # _orig_page_link = st.page_link
    # _orig_toggle = st.toggle
    # _orig_camera_input = st.camera_input
    _orig_chat_input = st.chat_input
    # _orig_searchbox = st_searchbox

    _orig_sidebar_button = st.sidebar.button
    _orig_sidebar_checkbox = st.sidebar.checkbox
    _orig_sidebar_radio = st.sidebar.radio
    _orig_sidebar_selectbox = st.sidebar.selectbox
    _orig_sidebar_multiselect = st.sidebar.multiselect
    _orig_sidebar_slider = st.sidebar.slider
    _orig_sidebar_select_slider = st.sidebar.select_slider
    _orig_sidebar_text_input = st.sidebar.text_input
    _orig_sidebar_number_input = st.sidebar.number_input
    _orig_sidebar_text_area = st.sidebar.text_area
    _orig_sidebar_date_input = st.sidebar.date_input
    _orig_sidebar_time_input = st.sidebar.time_input
    _orig_sidebar_file_uploader = st.sidebar.file_uploader
    _orig_sidebar_color_picker = st.sidebar.color_picker
    # _orig_sidebar_searchbox = st.sidebar.st_searchbox
    # new elements, testing
    # _orig_sidebar_download_button = st.sidebar.download_button
    # _orig_sidebar_link_button = st.sidebar.link_button
    # _orig_sidebar_page_link = st.sidebar.page_link
    # _orig_sidebar_toggle = st.sidebar.toggle
    # _orig_sidebar_camera_input = st.sidebar.camera_input
