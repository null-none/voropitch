import streamlit as st
from streamlit_drawable_canvas import st_canvas
import pandas as pd
from mplsoccer import Pitch
from helpers import (
    VoronoiPitch,
    Play,
    PitchImage,
    get_table_download_link,
    stroke_to_hex,
)
from pitch import FootballPitch

colors = {
    "black": "#000000",
    "blue": "#0000ff",
    "brown": "#a52a2a",
    "cyan": "#00ffff",
    "grey": "#808080",
    "green": "#008000",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "orange": "#ffa500",
    "pink": "#ffc0cb",
    "red": "#ff0000",
    "white": "#ffffff",
    "yellow": "#ffff00",
}

st.set_page_config(page_title="Voropitch", layout="wide")
st.title("Upload Image or Video")
uploaded_file = st.file_uploader(
    "Select Image file to open:", type=["png", "jpg", "mp4"]
)
football_pitch = FootballPitch()

if uploaded_file:
    upload_key = f"{uploaded_file.name}:{uploaded_file.size}"
    if st.session_state.get("upload_key") != upload_key:
        st.session_state.upload_key = upload_key
        st.session_state.lines_ready = False
        st.session_state.pop("line_objects", None)

    if uploaded_file.type == "video/mp4":
        play = Play(uploaded_file)
        t = st.slider(
            "You have uploaded a video. Choose the frame you want to process:",
            0.0,
            60.0,
        )
        image = PitchImage(football_pitch, image=play.get_frame(t))
    else:
        image = PitchImage(football_pitch, image_bytes=uploaded_file)

    st.title("Pitch lines")

    lines_expander = st.expander(
        "Draw pitch lines on selected image (2 horizontal lines, then 2 vertical lines)",
        expanded=True,
    )
    with lines_expander:
        col1, col2, col_, col3 = st.columns([2, 1, 0.5, 1])

        line_seq = ["UP", "DP", "RPA", "RG"]
        h_line_options = list(football_pitch.horiz_lines.keys())
        v_line_options = list(football_pitch.vert_lines.keys())

        with col2:
            hlines = [
                st.selectbox(
                    f"Horizontal Line #{x+1}",
                    h_line_options,
                    key=f"hline {x}",
                    index=h_line_options.index(line_seq[x]),
                )
                for x in range(2)
            ]
            vlines = [
                st.selectbox(
                    f"Vertical Line #{x+1}",
                    v_line_options,
                    key=f"vline {x}",
                    index=v_line_options.index(line_seq[x + 2]),
                )
                for x in range(2)
            ]

        with col3:
            st.image("pitch.png", width=300)

        lines_ready = st.session_state.get("lines_ready", False)
        line_objects = st.session_state.get("line_objects")

        if not lines_ready:
            with col1:
                canvas_image = st_canvas(
                    fill_color="rgba(255, 165, 0, 0.3)",
                    stroke_width=2,
                    stroke_color="#e00",
                    background_image=image.im,
                    width=image.im.width,
                    height=image.im.height,
                    drawing_mode="line",
                    key="canvas",
                )
            if canvas_image.json_data is not None:
                n_lines = len(canvas_image.json_data["objects"])
                with col3:
                    st.write(
                        f"You have drawn {n_lines} lines. "
                        + "Use the Undo button to delete lines."
                    )
                if n_lines >= 4:
                    st.session_state.line_objects = canvas_image.json_data["objects"]
                    st.session_state.lines_ready = True
                    st.rerun()
        else:
            with col1:
                st.image(image.im)
                if st.button("Redraw pitch lines"):
                    st.session_state.lines_ready = False
                    st.session_state.pop("line_objects", None)
                    st.rerun()

    if st.session_state.get("lines_ready"):
        image.set_info(
            pd.json_normalize(st.session_state.line_objects),
            hlines + vlines,
        )

        with lines_expander:
            st.write("Converted image:")
            st.image(image.conv_im)

        st.title("Players")
        st.write(
            "Draw rectangle over players on image. "
            + "The player location is assumed to be the middle of the base of the rectangle."
        )

        p_col1, p_col2, p_col_, p_col3 = st.columns([2, 1, 0.5, 1])

        with p_col2:
            team_color = st.selectbox("Team color: ", list(colors.keys()))
            stroke_color = colors[team_color]
            edit = st.checkbox("Edit mode (move selection boxes)")

        with p_col1:
            canvas_players = st_canvas(
                fill_color="rgba(255, 165, 0, 0.3)",
                stroke_width=2,
                stroke_color=stroke_color,
                background_image=image.im,
                drawing_mode="transform" if edit else "rect",
                height=image.im.height,
                width=image.im.width,
                key="canvas_players",
            )

        dfCoords = pd.DataFrame(columns=["team", "x", "y"])

        if canvas_players.json_data is not None:
            if len(canvas_players.json_data["objects"]) > 0:
                dfCoords = pd.json_normalize(canvas_players.json_data["objects"])
                dfCoords["x"] = (
                    dfCoords["left"] + (dfCoords["width"] * dfCoords["scaleX"]) / 2
                )
                dfCoords["y"] = (
                    dfCoords["top"] + dfCoords["height"] * dfCoords["scaleY"]
                )
                dfCoords[["x", "y"]] = image.h.apply_to_points(
                    dfCoords[["x", "y"]].values
                )
                dfCoords[["x", "y"]] = dfCoords[["x", "y"]] / image.h.coord_converter
                dfCoords["team"] = dfCoords["stroke"].apply(
                    lambda stroke: stroke_to_hex(stroke, colors)
                )
                dfCoords = dfCoords.dropna(subset=["team", "x", "y"])

            with p_col3:
                st.write("Player Coordinates:")
                if dfCoords.empty:
                    st.caption("Draw rectangles over players to see coordinates.")
                else:
                    st.dataframe(dfCoords[["team", "x", "y"]])

            if not dfCoords.empty:
                st.title("Final Output")
                voronoi = VoronoiPitch(dfCoords)
                ctrl_col, result_col = st.columns((1, 3))
                with ctrl_col:
                    show_voronoi = st.checkbox("Show Voronoi", value=False)
                    voronoi_opacity = int(
                        st.slider("Voronoi Opacity", 0, 100, value=35) * 2.55
                    )
                with result_col:
                    st.caption("Pitch with player positions")
                    mpl_pitch = Pitch(pitch_type="statsbomb", pitch_color="#22312b")
                    fig, ax = mpl_pitch.draw(figsize=(8, 5))
                    if show_voronoi:
                        voronoi.draw_on_mpl_axes(ax, opacity=voronoi_opacity)
                    mpl_pitch.scatter(
                        dfCoords.x,
                        dfCoords.y,
                        c=dfCoords.team,
                        s=120,
                        ax=ax,
                        edgecolors="white",
                        zorder=3,
                    )
                    st.pyplot(fig)

                df_output = dfCoords[["team", "x", "y"]]
                st.markdown(get_table_download_link(df_output), unsafe_allow_html=True)
