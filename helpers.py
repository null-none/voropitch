import base64
import tempfile

import cv2
import numpy as np
from itertools import product
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union


class Homography:
    def __init__(self, pts_src, pts_dst):
        self.pts_src = np.array(pts_src)
        self.pts_dst = np.array(pts_dst)
        self.h, _ = cv2.findHomography(self.pts_src, self.pts_dst)
        self.im_size = (525, 340)
        self.im_width = self.im_size[0]
        self.im_heigth = self.im_size[1]
        self.coord_converter = np.array(self.im_size) / 100 / np.array([1.2, 0.8])

    def apply_to_image(self, image):
        return cv2.warpPerspective(np.array(image.im), self.h, self.im_size)

    def apply_to_points(self, points, inverse=False):
        h = np.linalg.inv(self.h) if inverse else self.h
        _points = np.hstack([points, np.ones((len(points), 1))])
        _converted_points = np.dot(h, _points.T)
        points = _converted_points / _converted_points[2]
        return points[:2].T


class VoronoiPitch:
    def __init__(self, df):
        self.vor, self.df = calculate_voronoi(df)

    def get_regions(self):
        return [
            index
            for index, region in enumerate(self.vor.regions)
            if (-1 not in region) and (len(region) > 0)
        ]

    def get_points_region(self, region):
        return np.vstack([self.vor.vertices[i] for i in self.vor.regions[region]])

    def get_color_region(self, region):
        teams = self.df.loc[self.df["region"] == region, "team"].dropna()
        if teams.empty:
            return "#808080"
        return teams.values[0]

    def draw_on_mpl_axes(self, ax, opacity=89):
        from matplotlib.patches import Polygon as MplPolygon

        pitch_bounds = Polygon([(0, 0), (120, 0), (120, 80), (0, 80)])
        player_regions = set(self.df["region"].tolist())
        alpha = opacity / 255.0

        for region in self.get_regions():
            if region not in player_regions:
                continue
            cell = Polygon(self.get_points_region(region).tolist())
            clipped = pitch_bounds.intersection(cell)
            coords = _exterior_coords(clipped)
            if coords is None:
                continue
            ax.add_patch(
                MplPolygon(
                    coords,
                    closed=True,
                    facecolor=self.get_color_region(region),
                    edgecolor="none",
                    alpha=alpha,
                    zorder=1,
                )
            )


class Play:
    def __init__(self, uploaded_video):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        self._tmp.write(uploaded_video.getvalue())
        self._tmp.flush()
        self.video = cv2.VideoCapture(self._tmp.name)

    def get_frame(self, t):
        self.video.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        _, img = self.video.read()
        return img


class PitchImage:
    def __init__(self, pitch, image=None, image_bytes=None, width=600):
        if image is not None:
            im_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            self.im = self.resize(Image.fromarray(im_rgb), width=width)
        else:
            self.im = self.resize(Image.open(image_bytes), width=width)
        self.pitch = pitch

    def resize(self, im, width):
        return im.resize((width, int(width * im.height / im.width)))

    def set_info(self, df, lines):
        df["line"] = lines
        df["y1_line"] = df["top"] + df["y1"]
        df["y2_line"] = df["top"] + df["y2"]
        df["x1_line"] = df["left"] + df["x1"]
        df["x2_line"] = df["left"] + df["x2"]
        df["slope"], df["intercept"] = get_si_from_coords(
            df[["x1_line", "y1_line", "x2_line", "y2_line"]].values
        )
        df = df.set_index("line")
        self.df = df
        self.lines = lines
        self.h = Homography(*self.get_intersections())
        self.conv_im = Image.fromarray(self.h.apply_to_image(self))

    def get_intersections(self):
        vertical_lines = [x for x in self.lines if x in self.pitch.vert_lines]
        horizontal_lines = [x for x in self.lines if x in self.pitch.horiz_lines]
        intersections = {
            "_".join([v, h]): line_intersect(
                self.df.loc[v, ["slope", "intercept"]],
                self.df.loc[h, ["slope", "intercept"]],
            )
            for v, h in product(vertical_lines, horizontal_lines)
        }
        pts_src = list(intersections.values())
        pts_dst = [self.pitch.get_intersections()[x] for x in intersections]
        return pts_src, pts_dst


def line_intersect(si1, si2):
    m1, b1 = si1
    m2, b2 = si2
    if m1 == m2:
        return None
    x = (b2 - b1) / (m1 - m2)
    y = m1 * x + b1
    return x, y


def get_si_from_coords(lines):
    x1, y1, x2, y2 = lines.T
    slope = (y2 - y1) / (x2 - x1)
    intercept = y2 - slope * x2
    return slope, intercept


def calculate_voronoi(df):
    from scipy.spatial import Voronoi

    df = df.copy()
    values = np.vstack(
        (
            df[["x", "y"]].values,
            [-1000, -1000],
            [+1000, +1000],
            [+1000, -1000],
            [-1000, +1000],
        )
    )
    vor = Voronoi(values)
    df["region"] = vor.point_region[:-4]
    return vor, df


def _exterior_coords(geometry):
    if geometry.is_empty:
        return None
    if geometry.geom_type == "Polygon":
        polygon = geometry
    elif geometry.geom_type == "MultiPolygon":
        polygon = max(geometry.geoms, key=lambda part: part.area)
    elif geometry.geom_type == "GeometryCollection":
        parts = [
            g for g in geometry.geoms if g.geom_type in ("Polygon", "MultiPolygon")
        ]
        if not parts:
            return None
        return _exterior_coords(unary_union(parts))
    else:
        return None
    return np.vstack(polygon.exterior.xy).T


def stroke_to_hex(stroke, colors):
    if stroke is None or (isinstance(stroke, float) and np.isnan(stroke)):
        return None
    stroke = str(stroke).strip().lower()
    for name, code in colors.items():
        if stroke == code.lower() or stroke == name.lower():
            return code
    return None


def get_table_download_link(df):
    csv = df.to_csv(index=True)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="data.csv">Download csv file</a>'
