"""VAJB mf3 1.1 - read and change Creality Print / Orca style 3MF projects (RULES_3D_PRINTING.md D1, D2).

    from model3d import mf3
    p = mf3.open("ram_v10.3mf")
    p.objects                         # [Obj(id, name, verts, tris, settings, parts)]
    p.settings["sparse_infill_density"]   # project settings (Metadata/project_settings.config)
    p.set_object(name, sparse_infill_density="100%", brim_type="outer_only")
    p.set_project(layer_height="0.12")
    p.add_modifier(name, z0, z1, sparse_infill_density="100%")  # box over a height range
    p.replace_mesh(name, verts, tris)  # new geometry, same settings and place
    p.rename(old, new)
    p.postavi_objekte([(ime, verts, tris), ...])   # svi objekti zamenjeni novim (iste postavke projekta)
    p.save("ram_v11.3mf")             # writes a new file, the original is never changed

Works on the structure Creality Print 7.x writes (3D/3dmodel.model with components ->
3D/Objects/*.model, Metadata/model_settings.config, Metadata/project_settings.config).
Settings are written as text values the way the slicer stores them ("100%", "0.12").
"""
import io
import json
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NS_P = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
ET.register_namespace("", NS)
ET.register_namespace("p", NS_P)
Q = lambda t: f"{{{NS}}}{t}"


def _m(s):
    """3MF transform (12 numbers, row vectors) -> 4x3 matrix; None -> identity."""
    if not s:
        return np.vstack([np.eye(3), np.zeros(3)])
    return np.array([float(x) for x in s.split()]).reshape(4, 3)


@dataclass
class Part:
    id: str
    name: str
    subtype: str              # normal_part | modifier_part | negative_part | support_blocker ...
    settings: dict = field(default_factory=dict)


@dataclass
class Obj:
    id: str
    name: str
    verts: np.ndarray         # Nx3, world coordinates (on the plate)
    tris: np.ndarray          # Mx3
    settings: dict = field(default_factory=dict)
    parts: list = field(default_factory=list)
    mesh_path: str = ""       # 3D/Objects/xxx.model
    mesh_id: str = ""


class Project:
    def __init__(self, path):
        self.path = Path(path)
        with zipfile.ZipFile(self.path) as z:
            self.files = {n: z.read(n) for n in z.namelist()}
        self.model = ET.fromstring(self.files["3D/3dmodel.model"])
        ms = self.files.get("Metadata/model_settings.config")
        self.ms = ET.fromstring(ms) if ms else ET.Element("config")
        try:
            self.settings = json.loads(self.files.get("Metadata/project_settings.config", b"{}"))
        except ValueError:
            self.settings = {}
        # Creality Print 7: per-plate process overrides (Metadata/process_settings_N.config) win over the project
        self.plate_settings = {}
        for n, b in self.files.items():
            mm = re.match(r"Metadata/process_settings_(\d+)\.config$", n)
            if mm:
                try:
                    self.plate_settings[int(mm.group(1))] = json.loads(b)
                except ValueError:
                    pass  # namerno: pokvaren fajl ploče se preskače, projekat ostaje čitljiv
        self._submodels = {}
        self.objects = self._read_objects()

    # ---------- reading ----------
    def _sub(self, path):
        path = path.lstrip("/")
        if path not in self._submodels:
            self._submodels[path] = ET.fromstring(self.files[path])
        return self._submodels[path]

    def _mesh_of(self, root, oid):
        for o in root.iter(Q("object")):
            if o.get("id") == oid:
                m = o.find(Q("mesh"))
                if m is not None:
                    v = np.array([[float(x.get(a)) for a in "xyz"] for x in m.iter(Q("vertex"))], float)
                    t = np.array([[int(x.get(a)) for a in ("v1", "v2", "v3")] for x in m.iter(Q("triangle"))], int)
                    return v.reshape(-1, 3), t.reshape(-1, 3)
        return np.zeros((0, 3)), np.zeros((0, 3), int)

    def _ms_object(self, oid):
        for o in self.ms.iter("object"):
            if o.get("id") == oid:
                return o
        return None

    @staticmethod
    def _meta(el):
        return {m.get("key"): m.get("value") for m in el.findall("metadata")} if el is not None else {}

    def _read_objects(self):
        items = {i.get("objectid"): i.get("transform") for i in self.model.iter(Q("item"))}
        out = []
        for o in self.model.find(Q("resources")).iter(Q("object")):
            oid = o.get("id")
            if oid not in items:
                continue
            V, T, path, mid = [], [], "", ""
            mso0 = self._ms_object(oid)
            not_body = {pt.get("id") for pt in (mso0.findall("part") if mso0 is not None else [])
                        if pt.get("subtype", "normal_part") != "normal_part"}
            comps = o.find(Q("components"))
            if comps is not None:
                for c in comps.findall(Q("component")):
                    if c.get("objectid") in not_body:      # modifiers, negative parts: not the printed body
                        continue
                    path = c.get(f"{{{NS_P}}}path") or "3D/3dmodel.model"
                    mid = c.get("objectid")
                    v, t = self._mesh_of(self._sub(path) if path != "3D/3dmodel.model" else self.model, mid)
                    m = _m(c.get("transform"))
                    T.append(t + sum(len(x) for x in V))
                    V.append(v @ m[:3] + m[3])
            else:
                v, t = self._mesh_of(self.model, oid)
                V, T = [v], [t]
            v = np.vstack(V) if V else np.zeros((0, 3))
            m = _m(items[oid])
            v = v @ m[:3] + m[3]
            mso = self._ms_object(oid)
            meta = self._meta(mso)
            parts = [Part(p.get("id"), self._meta(p).get("name", ""), p.get("subtype", "normal_part"),
                          {k: v for k, v in self._meta(p).items() if k not in ("name", "matrix", "source_file",
                           "source_object_id", "source_volume_id", "source_offset_x", "source_offset_y",
                           "source_offset_z", "mesh_stat")})
                     for p in (mso.findall("part") if mso is not None else [])]
            name = meta.pop("name", o.get("name") or f"objekat {oid}")
            meta.pop("extruder", None)
            out.append(Obj(oid, name, v, np.vstack(T) if T else np.zeros((0, 3), int), meta, parts, path, mid))
        return out

    def get(self, name):
        for o in self.objects:
            if o.name == name:
                return o
        raise KeyError(f"nema objekta „{name}“ (ima: {', '.join(x.name for x in self.objects)})")

    # ---------- changing ----------
    def set_project(self, **kv):
        """Project value; where a plate overrides the same key, the plate gets it too (else it would not apply)."""
        self.settings.update({k: str(v) for k, v in kv.items()})
        for ps in self.plate_settings.values():
            for k, v in kv.items():
                if k in ps:
                    ps[k] = str(v)

    def effective(self, key, obj=None, plate=1):
        """Value the slicer uses: object > plate > project."""
        if obj is not None and key in obj.settings:
            return obj.settings[key]
        if key in self.plate_settings.get(plate, {}):
            return self.plate_settings[plate][key]
        v = self.settings.get(key, "")
        return v[0] if isinstance(v, list) and v else v

    def set_object(self, name, **kv):
        o = self.get(name)
        mso = self._ms_object(o.id)
        if mso is None:
            mso = ET.SubElement(self.ms, "object", id=o.id)
            ET.SubElement(mso, "metadata", key="name", value=name)
        for k, v in kv.items():
            el = next((m for m in mso.findall("metadata") if m.get("key") == k), None)
            if el is None:
                el = ET.Element("metadata", key=k)
                idx = next((i for i, c in enumerate(list(mso)) if c.tag == "part"), len(mso))
                mso.insert(idx, el)
            el.set("value", str(v))
            o.settings[k] = str(v)

    def rename(self, old, new):
        o = self.get(old)
        mso = self._ms_object(o.id)
        for m in (mso.findall("metadata") if mso is not None else []):
            if m.get("key") == "name":
                m.set("value", new)
        for x in self.model.iter(Q("object")):
            if x.get("id") == o.id and x.get("name"):
                x.set("name", new)
        o.name = new

    def replace_mesh(self, name, verts, tris):
        """New geometry in world coordinates; stored relative to the object's current transform."""
        o = self.get(name)
        item = next(i for i in self.model.iter(Q("item")) if i.get("objectid") == o.id)
        m = _m(item.get("transform"))
        comp = next((c for x in self.model.iter(Q("object")) if x.get("id") == o.id
                     for c in x.iter(Q("component"))), None)
        if comp is not None:
            cm = _m(comp.get("transform"))
            m = np.vstack([cm[:3] @ m[:3], cm[3] @ m[:3] + m[3]])
        local = (np.asarray(verts, float) - m[3]) @ np.linalg.inv(m[:3])
        root = self._sub(o.mesh_path) if o.mesh_path and o.mesh_path != "3D/3dmodel.model" else self.model
        mesh_obj = next(x for x in root.iter(Q("object")) if x.get("id") == (o.mesh_id or o.id))
        mesh = mesh_obj.find(Q("mesh"))
        mesh_obj.remove(mesh)
        mesh = ET.SubElement(mesh_obj, Q("mesh"))
        vs, ts = ET.SubElement(mesh, Q("vertices")), ET.SubElement(mesh, Q("triangles"))
        for x, y, z in local:
            ET.SubElement(vs, Q("vertex"), x=f"{x:.6g}", y=f"{y:.6g}", z=f"{z:.6g}")
        for a, b, c in np.asarray(tris, int):
            ET.SubElement(ts, Q("triangle"), v1=str(a), v2=str(b), v3=str(c))
        o.verts, o.tris = np.asarray(verts, float), np.asarray(tris, int)

    def add_modifier(self, name, z0, z1, **kv):
        """Modifier box over the whole object between heights z0..z1 (world mm), with its own settings.
        Typical use: sparse_infill_density="100%" over a slot or a hook (D5)."""
        o = self.get(name)
        lo, hi = o.verts.min(0) - 1, o.verts.max(0) + 1
        box_v = np.array([[x, y, z] for z in (z0, z1) for y in (lo[1], hi[1]) for x in (lo[0], hi[0])], float)
        box_t = np.array([[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4],
                          [2, 6, 3], [3, 6, 7], [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5]])
        item = next(i for i in self.model.iter(Q("item")) if i.get("objectid") == o.id)
        m = _m(item.get("transform"))
        local = (box_v - m[3]) @ np.linalg.inv(m[:3])
        obj_el = next(x for x in self.model.find(Q("resources")).iter(Q("object")) if x.get("id") == o.id)
        comps = obj_el.find(Q("components"))
        if comps is None:
            raise ValueError("objekat bez komponenti: modifikator za ovaj oblik 3MF-a nije podržan")
        path = o.mesh_path or "3D/Objects/object_1.model"
        root = self._sub(path)
        ids = [int(x.get("id")) for x in root.iter(Q("object"))] + [int(x.get("id")) for x in self.model.iter(Q("object"))]
        nid = str(max(ids) + 1)
        res = root.find(Q("resources"))
        new = ET.SubElement(res, Q("object"), id=nid, type="model")
        mesh = ET.SubElement(new, Q("mesh"))
        vs, ts = ET.SubElement(mesh, Q("vertices")), ET.SubElement(mesh, Q("triangles"))
        for x, y, z in local:
            ET.SubElement(vs, Q("vertex"), x=f"{x:.6g}", y=f"{y:.6g}", z=f"{z:.6g}")
        for a, b, c in box_t:
            ET.SubElement(ts, Q("triangle"), v1=str(a), v2=str(b), v3=str(c))
        c = ET.SubElement(comps, Q("component"), objectid=nid, transform="1 0 0 0 1 0 0 0 1 0 0 0")
        c.set(f"{{{NS_P}}}path", "/" + path.lstrip("/"))
        c.set(f"{{{NS_P}}}UUID", str(uuid.uuid4()))
        new.set(f"{{{NS_P}}}UUID", str(uuid.uuid4()))
        mso = self._ms_object(o.id)
        part = ET.SubElement(mso, "part", id=nid, subtype="modifier_part")
        ET.SubElement(part, "metadata", key="name", value=f"modifikator {z0:g}-{z1:g} mm")
        ET.SubElement(part, "metadata", key="matrix", value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1")
        for k, v in kv.items():
            ET.SubElement(part, "metadata", key=k, value=str(v))
        o.parts.append(Part(nid, f"modifikator {z0:g}-{z1:g} mm", "modifier_part", {k: str(v) for k, v in kv.items()}))
        return nid

    def postavi_objekte(self, objekti, ploca=1):
        """Zameni SVE objekte projekta novim telima (svet. koordinate, z od 0) - podesavanja projekta,
        ploce i stampaca ostaju (D11). Svaki objekat dobija svoj 3D/Objects/object_N.model, ime = ime dela."""
        res, build = self.model.find(Q("resources")), self.model.find(Q("build"))
        for o in list(res):
            res.remove(o)
        for it in list(build):
            build.remove(it)
        for n in [n for n in self.files if n.startswith("3D/Objects/")]:
            del self.files[n]
        self._submodels = {}
        for o in list(self.ms.findall("object")):
            self.ms.remove(o)
        plate = self.ms.find("plate")
        if plate is None:
            plate = ET.SubElement(self.ms, "plate")
            ET.SubElement(plate, "metadata", key="plater_id", value=str(ploca))
        for mi in list(plate.findall("model_instance")):
            plate.remove(mi)
        asm = self.ms.find("assemble")
        if asm is None:
            asm = ET.SubElement(self.ms, "assemble")
        for a in list(asm):
            asm.remove(a)
        rels = []
        self.objects = []
        for k, (ime, verts, tris) in enumerate(objekti):
            v = np.asarray(verts, float)
            t = np.asarray(tris, int)
            c = np.array([(v[:, 0].min() + v[:, 0].max()) / 2, (v[:, 1].min() + v[:, 1].max()) / 2, v[:, 2].min()])
            loc = v - c
            oid, mid = str(2 * k + 2), str(2 * k + 1)
            path = f"3D/Objects/object_{k + 1}.model"
            sub = ET.Element(Q("model"), unit="millimeter")
            sub.set("requiredextensions", "p")
            sres = ET.SubElement(sub, Q("resources"))
            so = ET.SubElement(sres, Q("object"), id=mid, type="model")
            so.set(f"{{{NS_P}}}UUID", str(uuid.uuid4()))
            mesh = ET.SubElement(so, Q("mesh"))
            vs, ts = ET.SubElement(mesh, Q("vertices")), ET.SubElement(mesh, Q("triangles"))
            for x, y, z in loc:
                ET.SubElement(vs, Q("vertex"), x=f"{x:.6g}", y=f"{y:.6g}", z=f"{z:.6g}")
            for a, b, cc in t:
                ET.SubElement(ts, Q("triangle"), v1=str(a), v2=str(b), v3=str(cc))
            ET.SubElement(sub, Q("build"))
            self._submodels[path] = sub
            self.files[path] = b""
            o = ET.SubElement(res, Q("object"), id=oid, type="model")
            o.set(f"{{{NS_P}}}UUID", str(uuid.uuid4()))
            comps = ET.SubElement(o, Q("components"))
            comp = ET.SubElement(comps, Q("component"), objectid=mid, transform="1 0 0 0 1 0 0 0 1 0 0 0")
            comp.set(f"{{{NS_P}}}path", "/" + path)
            comp.set(f"{{{NS_P}}}UUID", str(uuid.uuid4()))
            tr = f"1 0 0 0 1 0 0 0 1 {c[0]:.4f} {c[1]:.4f} {c[2]:.4f}"
            it = ET.SubElement(build, Q("item"), objectid=oid, transform=tr, printable="1")
            it.set(f"{{{NS_P}}}UUID", str(uuid.uuid4()))
            mo = ET.SubElement(self.ms, "object", id=oid)
            ET.SubElement(mo, "metadata", key="name", value=ime)
            ET.SubElement(mo, "metadata", key="extruder", value="1")
            pt = ET.SubElement(mo, "part", id=mid, subtype="normal_part")
            ET.SubElement(pt, "metadata", key="name", value=ime)
            ET.SubElement(pt, "metadata", key="matrix", value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1")
            mi = ET.SubElement(plate, "model_instance")
            ET.SubElement(mi, "metadata", key="object_id", value=oid)
            ET.SubElement(mi, "metadata", key="instance_id", value="0")
            ET.SubElement(mi, "metadata", key="identify_id", value=str(100 + k))
            ET.SubElement(asm, "assemble_item", object_id=oid, instance_id="0",
                          transform=tr, offset="0 0 0")
            rels.append(path)
            self.objects.append(Obj(oid, ime, v, t, {}, [Part(mid, ime, "normal_part")], path, mid))
        # veze ka podmodelima
        rel = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
               + "".join(f' <Relationship Target="/{p}" Id="rel-{i + 1}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
                         for i, p in enumerate(rels)) + "</Relationships>\n")
        self.files["3D/_rels/3dmodel.model.rels"] = rel.encode()
        # stare slicice ploce vise ne odgovaraju
        for n in [n for n in self.files if re.match(r"Metadata/(plate|pick|top|plate_no_light)_\d+(_small)?\.png$", n)]:
            del self.files[n]
        for k in ("thumbnail_file", "thumbnail_no_light_file", "top_file", "pick_file"):
            for m in plate.findall("metadata"):
                if m.get("key") == k:
                    plate.remove(m)

    def _xml(self, name, root):
        """Serialize and put back namespace declarations ElementTree drops (Creality writes
        xmlns:BambuStudio and requiredextensions="p"; the slicer may expect them)."""
        out = ET.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")
        orig = self.files.get(name, b"").decode("utf-8", "replace")
        m = re.search(r"<(?:\w+:)?(model|config)\b[^>]*>", orig)
        if m:
            decls = dict(re.findall(r'xmlns(?::(\w+))?="([^"]+)"', m.group(0)))
            tag = re.search(r"<(?:\w+:)?(model|config)\b[^>]*>", out)
            head = tag.group(0)
            add = "".join(f' xmlns{":" + k if k else ""}="{v}"' for k, v in decls.items()
                          if f'xmlns{":" + k if k else ""}=' not in head)
            for attr in ("requiredextensions", "xml:lang"):
                am = re.search(rf'{attr}="([^"]*)"', m.group(0))
                if am and attr + "=" not in head:
                    add += f' {attr}="{am.group(1)}"'
            out = out.replace(head, head[:-1] + add + ">", 1) if not head.endswith("/>") else out
        return out.encode("utf-8")

    def save(self, path):
        path = Path(path)
        if path.resolve() == self.path.resolve():
            raise ValueError("original se ne menja: sačuvaj pod novim imenom (npr. _vN+1)")
        files = dict(self.files)
        files["3D/3dmodel.model"] = self._xml("3D/3dmodel.model", self.model)
        for p, root in self._submodels.items():
            files[p] = self._xml(p, root)
        files["Metadata/model_settings.config"] = ET.tostring(self.ms, xml_declaration=True, encoding="UTF-8")
        files["Metadata/project_settings.config"] = json.dumps(self.settings, indent=4, ensure_ascii=False).encode()
        for n, ps in self.plate_settings.items():
            files[f"Metadata/process_settings_{n}.config"] = json.dumps(ps, indent=4, ensure_ascii=False).encode()
        tmp = path.with_suffix(".saving")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for n, b in files.items():
                z.writestr(n, b)
        tmp.replace(path)
        return path


def open(path):  # namerno isto ime kao ugrađeni open()
    return Project(path)
