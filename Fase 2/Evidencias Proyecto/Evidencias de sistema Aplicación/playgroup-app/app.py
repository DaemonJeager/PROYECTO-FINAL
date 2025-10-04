from sqlalchemy import create_engine, Column, Integer, String, Date, Time, DateTime, Boolean
from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, time, timedelta, date
import os, re
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
load_dotenv(override=True) 

BUSINESS_START = time(9, 0)   # 09:00
BUSINESS_END   = time(18, 0)  # 18:00


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Falta DATABASE_URL en .env")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False, future=True, fast_executemany=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class Child(Base):
    __tablename__ = "Child"
    __table_args__ = {"schema": "pg"}
    ChildId = Column(Integer, primary_key=True)
    FirstName = Column(String(80), nullable=False)
    LastName = Column(String(80), nullable=False)
    BirthDate = Column(Date, nullable=False)
    Notes = Column(String(500))
    
class User(Base):
    __tablename__ = "User"
    __table_args__ = {"schema": "pg"}
    UserId = Column(Integer, primary_key=True)
    Email = Column(String(120), nullable=False)
    PasswordHash = Column(String(255), nullable=False)
    Role = Column(String(20), nullable=False)
    FirstName = Column(String(80), nullable=False)
    LastName  = Column(String(80), nullable=False)
    Phone     = Column(String(30))

class Guardian(Base):
    __tablename__ = "Guardian"
    __table_args__ = {"schema": "pg"}
    GuardianId = Column(Integer, primary_key=True)
    UserId = Column(Integer, nullable=True)
    PreferredContact = Column(String(20))
    IsActive = Column(Integer)  # 1/0

class ChildGuardian(Base):
    __tablename__ = "ChildGuardian"
    __table_args__ = {"schema": "pg"}
    ChildId = Column(Integer, primary_key=True)
    GuardianId = Column(Integer, primary_key=True)
    Relation = Column(String(40))
    IsPrimary = Column(Integer)  # 1/0
class AvailabilityBlock(Base):
    __tablename__ = "AvailabilityBlock"
    __table_args__ = {"schema": "pg"}
    AvailabilityId   = Column(Integer, primary_key=True)
    TherapistUserId  = Column(Integer, nullable=False)
    Weekday          = Column(Integer, nullable=False)  # 0=Lun ... 6=Dom
    StartTime        = Column(Time, nullable=False)
    EndTime          = Column(Time, nullable=False)
    IsActive         = Column(Boolean, nullable=False, default=True)

class PgSession(Base):
    __tablename__ = "Session"
    __table_args__ = {"schema": "pg"}
    SessionId        = Column(Integer, primary_key=True)
    GroupId          = Column(Integer)       # opcional
    TherapistUserId  = Column(Integer, nullable=False)
    ScheduledAt      = Column(DateTime, nullable=False)
    DurationMin      = Column(Integer, nullable=False)
    GoalSummary      = Column(String(255))
    Notes            = Column(String(2000))
    CreatedByUserId  = Column(Integer, nullable=False)
    CreatedAt        = Column(DateTime, nullable=False)


def create_app():
    # fuerza carpetas
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")

    @app.get("/_db")
    def db_ping():
        # prueba de conexión simple
        from sqlalchemy import text
        with engine.connect() as conn:
            row = conn.execute(text("SELECT TOP 1 Name FROM pg.ActivityCatalog ORDER BY ActivityId")).first()
        return f"DB OK -> {row[0] if row else 'sin filas'}"

    @app.get("/")
    def home():
        return redirect(url_for("children_list"))

    @app.get("/children")
    def children_list():
        with SessionLocal() as db:
            rows = db.query(Child).order_by(Child.LastName, Child.FirstName).all()
        return render_template("children_list.html", children=rows)

    @app.route("/children/new", methods=["GET", "POST"])
    def children_new():
       if request.method == "POST":
         fn = request.form.get("FirstName", "").strip()
         ln = request.form.get("LastName", "").strip()
         bd = request.form.get("BirthDate", "").strip()
         notes = request.form.get("Notes", "").strip() or None

         if not fn or not ln or not bd:
            flash("Nombre, Apellido y Fecha de Nacimiento son obligatorios.", "danger")
            return redirect(url_for("children_new"))

         try:
            y, m, d = map(int, bd.split("-"))
            born = date(y, m, d)
         except Exception:
            flash("Fecha inválida. Usa formato YYYY-MM-DD.", "danger")
            return redirect(url_for("children_new"))

         with SessionLocal() as db:
            c = Child(FirstName=fn, LastName=ln, BirthDate=born, Notes=notes)
            db.add(c)
            db.commit()
            flash("Niño creado correctamente.", "success")
         return redirect(url_for("children_list"))

    # GET
       return render_template("children_form.html", mode="new", child=None)

    @app.route("/children/<int:child_id>/edit", methods=["GET", "POST"])
    def children_edit(child_id: int):
      with SessionLocal() as db:
        c = db.get(Child, child_id)
        if not c:
            flash("Niño no encontrado.", "warning")
            return redirect(url_for("children_list"))

        if request.method == "POST":
            fn = request.form.get("FirstName", "").strip()
            ln = request.form.get("LastName", "").strip()
            bd = request.form.get("BirthDate", "").strip()
            notes = request.form.get("Notes", "").strip() or None

            if not fn or not ln or not bd:
                flash("Nombre, Apellido y Fecha son obligatorios.", "danger")
                return redirect(url_for("children_edit", child_id=child_id))

            try:
                y, m, d = map(int, bd.split("-"))
                c.BirthDate = date(y, m, d)
            except Exception:
                flash("Fecha inválida. Usa YYYY-MM-DD.", "danger")
                return redirect(url_for("children_edit", child_id=child_id))

            c.FirstName = fn
            c.LastName = ln
            c.Notes = notes
            db.commit()
            flash("Niño actualizado.", "success")
            return redirect(url_for("children_list"))

    # GET
      return render_template("children_form.html", mode="edit", child=c)
    @app.post("/children/<int:child_id>/delete")
    def children_delete(child_id: int):
        with SessionLocal() as db:
         c = db.get(Child, child_id)
         if not c:
             flash("Niño no encontrado.", "warning")
             return redirect(url_for("children_list"))
         db.delete(c)
         db.commit()
         flash("Niño eliminado.", "success")
        return redirect(url_for("children_list"))
    
    # -------- Apoderados --------
    @app.get("/guardians")
    def guardians_list():
            with SessionLocal() as db:
                rows = (db.query(Guardian, User)
                     .join(User, Guardian.UserId == User.UserId)
                     .order_by(User.LastName, User.FirstName)
                     .all())
            return render_template("guardians_list.html", guardians=rows)
                 
    @app.route("/guardians/new", methods=["GET","POST"])
    def guardians_new():
            if request.method == "POST":
                fn = request.form.get("FirstName","").strip()
                ln = request.form.get("LastName","").strip()
                email = request.form.get("Email","").strip()
                phone = request.form.get("Phone","").strip() or None
                pref = request.form.get("PreferredContact","email")
                if not fn or not ln or not email:
                  flash("Nombre, Apellido y Email son obligatorios.", "danger")
                  return redirect(url_for("guardians_new"))
                try:
                  with SessionLocal() as db:
                      u = User(Email=email, PasswordHash="TEMP", Role="guardian",
                           FirstName=fn, LastName=ln, Phone=phone)
                      db.add(u); db.flush()
                      g = Guardian(UserId=u.UserId, PreferredContact=pref, IsActive=1)
                      db.add(g); db.commit()
                  flash("Apoderado creado.", "success")
                  return redirect(url_for("guardians_list"))
                except IntegrityError:
                    flash("Ese email ya existe.", "danger")
                    return redirect(url_for("guardians_new"))
            return render_template("guardian_form.html", mode="new", data=None)
    
    @app.route("/guardians/<int:gid>/edit", methods=["GET","POST"])
    def guardians_edit(gid:int):
            with SessionLocal() as db:
                 g = db.get(Guardian, gid)
                 if not g: flash("No encontrado.", "warning"); return redirect(url_for("guardians_list"))
                 u = db.get(User, g.UserId)
                 if request.method == "POST":
                    u.FirstName = request.form.get("FirstName","").strip()
                    u.LastName  = request.form.get("LastName","").strip()
                    u.Email     = request.form.get("Email","").strip()
                    u.Phone     = request.form.get("Phone","").strip() or None
                    g.PreferredContact = request.form.get("PreferredContact","email")
                    try: db.commit(); flash("Actualizado.", "success")
                    except IntegrityError: db.rollback(); flash("Email duplicado.", "danger")
                    return redirect(url_for("guardians_list"))
            data = {"FirstName":u.FirstName,"LastName":u.LastName,"Email":u.Email,
                   "Phone":u.Phone,"PreferredContact":g.PreferredContact}
            return render_template("guardian_form.html", mode="edit", data=data, gid=gid)
    @app.post("/guardians/<int:gid>/delete")
    def guardians_delete(gid:int):
        with SessionLocal() as db:
            g = db.get(Guardian, gid)
            if not g: flash("No encontrado.", "warning"); return redirect(url_for("guardians_list"))
            g.IsActive = 0
            db.commit()
            flash("Apoderado desactivado.", "success")
        return redirect(url_for("guardians_list"))
    
    # -------- Vínculo Niño–Apoderado --------
    @app.route("/children/<int:child_id>/guardians", methods=["GET","POST"])
    def child_guardians(child_id:int):
        with SessionLocal() as db:
            child = db.get(Child, child_id)
            if not child: flash("Niño no encontrado.", "warning"); return redirect(url_for("children_list"))

            if request.method == "POST":
                gid = int(request.form.get("GuardianId"))
                rel = request.form.get("Relation","").strip() or None
                is_primary = 1 if request.form.get("IsPrimary")=="on" else 0
                if not db.query(ChildGuardian).filter_by(ChildId=child_id, GuardianId=gid).first():
                     db.add(ChildGuardian(ChildId=child_id, GuardianId=gid, Relation=rel, IsPrimary=is_primary))
                     db.commit(); flash("Vínculo creado.", "success")
                else:
                      flash("Ya está vinculado.", "warning")
                return redirect(url_for("child_guardians", child_id=child_id))

            assigned = (db.query(ChildGuardian, Guardian, User)
                         .join(Guardian, ChildGuardian.GuardianId==Guardian.GuardianId)
                         .join(User, Guardian.UserId==User.UserId)
                         .filter(ChildGuardian.ChildId==child_id)
                        .order_by(User.LastName, User.FirstName).all())
            sub = db.query(ChildGuardian.GuardianId).filter(ChildGuardian.ChildId==child_id)
            available = (db.query(Guardian, User)
                          .join(User, Guardian.UserId==User.UserId)
                          .filter(Guardian.IsActive==1, ~Guardian.GuardianId.in_(sub))
                        .order_by(User.LastName, User.FirstName).all())
        return render_template("child_guardians.html", child=child, assigned=assigned, available=available)
        
           
    @app.post("/children/<int:child_id>/guardians/<int:gid>/remove")
    def child_guardians_remove(child_id:int, gid:int):
        with SessionLocal() as db:
            cg = db.query(ChildGuardian).filter_by(ChildId=child_id, GuardianId=gid).first()
            if cg: db.delete(cg); db.commit(); flash("Vínculo eliminado.", "success")
            else:  flash("Vínculo no encontrado.", "warning")
        return redirect(url_for("child_guardians", child_id=child_id))
        
        
        # -------- TERAPEUTAS (usamos pg.User con Role='therapist') --------
    @app.get("/therapists")
    def therapists_list():
        with SessionLocal() as db:
          rows = db.query(User).filter(User.Role == "therapist").order_by(User.LastName, User.FirstName).all()
        return render_template("therapists_list.html", therapists=rows)
        
    @app.route("/therapists/new", methods=["GET","POST"])
    def therapists_new():
        if request.method == "POST":
            fn = request.form.get("FirstName","").strip()
            ln = request.form.get("LastName","").strip()
            email = request.form.get("Email","").strip()
            phone = request.form.get("Phone","").strip() or None
            if not fn or not ln or not email:
                flash("Nombre, Apellido y Email son obligatorios.", "danger")
                return redirect(url_for("therapists_new"))
            from sqlalchemy.exc import IntegrityError
            try:
                 with SessionLocal() as db:
                     u = User(Email=email, PasswordHash="TEMP", Role="therapist",
                              FirstName=fn, LastName=ln, Phone=phone)
                     db.add(u)
                     db.commit()
                 flash("Terapeuta creado.", "success")
                 return redirect(url_for("therapists_list"))
            except IntegrityError:
                 flash("Ese email ya existe.", "danger")
                 return redirect(url_for("therapists_new"))
        return render_template("therapist_form.html", mode="new", data=None) 
             
    @app.route("/therapists/<int:uid>/edit", methods=["GET","POST"])
    def therapists_edit(uid:int):       
            with SessionLocal() as db:
              u = db.get(User, uid)
              if not u or u.Role != "therapist":
                 flash("Terapeuta no encontrado.", "warning")
                 return redirect(url_for("therapists_list"))
              
              if request.method == "POST":
                  u.FirstName = request.form.get("FirstName","").strip()
                  u.LastName  = request.form.get("LastName","").strip()
                  u.Email     = request.form.get("Email","").strip()
                  u.Phone     = request.form.get("Phone","").strip() or None
                  try:
                      db.commit()
                      flash("Terapeuta actualizado.", "success")
                  except IntegrityError:
                      db.rollback()
                      flash("Ese email ya existe.", "danger")
                  return redirect(url_for("therapists_list"))
            
            data = {"FirstName":u.FirstName,"LastName":u.LastName,"Email":u.Email,"Phone":u.Phone}
            return render_template("therapist_form.html", mode="edit", data=data, uid=uid)
        
    @app.post("/therapists/<int:uid>/delete")
    def therapists_delete(uid:int):
            with SessionLocal() as db:
                u = db.get(User, uid)
                if not u or u.Role != "therapist":
                   flash("Terapeuta no encontrado.", "warning")
                   return redirect(url_for("therapists_list"))
        #cambiamos el rol para ocultarlo de la lista
                u.Role = "therapist_inactive"
                db.commit()
                flash("Terapeuta desactivado.", "success")
            return redirect(url_for("therapists_list"))
             
             
             
             
    WEEK_LABELS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    
    
    def _parse_time(s: str) -> time:
        s = (s or "").strip()
        s = s.replace(";", ":").replace(".", ":")
        
        m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
        if not m:
            raise ValueError("Formato de hora inválido. Usa HH:MM")
        
        h = int(m.group(1))
        m_ = int(m.group(2))
        s_ = int(m.group(3) or 0)
        
        if not (0 <= h <= 23 and 0 <= m_ <= 59 and 0 <= s_ <= 59):
             raise ValueError("Hora fuera de rango (00:00–23:59).")
        return time(h, m_, s_)
    
    
    @app.route("/therapists/<int:uid>/availability", methods=["GET","POST"])
    def therapist_availability(uid:int):
        # validar que existe y es therapist
        with SessionLocal() as db:
            u = db.get(User, uid)
            if not u or u.Role not in ("therapist","therapist_inactive"):
                flash("Terapeuta no encontrado.", "warning")
                return redirect(url_for("therapists_list"))

            if request.method == "POST":
                #lee datos
                    weekday_str = (request.form.get("Weekday") or "").strip()
                    st_str = (request.form.get("StartTime") or "").strip()
                    et_str = (request.form.get("EndTime") or "").strip()
                    
                    try: 
                        weekday = int(weekday_str)
                    except ValueError:
                        flash("seleccione el dia", "danger")
                        return redirect(url_for("therapist_availability", uid=uid))
                    if weekday < 0 or weekday > 6:
                        flash("Dia invalido", "danger")
                        return redirect(url_for("therapist_availability", uid=uid))
                    
                    try:
                        start_t = _parse_time(st_str)
                        end_t = _parse_time(et_str)
                    except ValueError as e:
                        flash(str(e), "danger")
                        return redirect(url_for("therapist_availability", uid=uid))
                   
                    if start_t < BUSINESS_START or end_t > BUSINESS_END:
                        flash("Los bloques deben estar entre 09:00 y 18:00.", "danger")
                        return redirect(url_for("therapist_availability", uid=uid))
                    
                    if start_t >= end_t:
                        flash("La hora de fin debe ser mayor a la de inicio.", "danger")
                        return redirect(url_for("therapist_availability", uid=uid))
                   
                        # (opcional) evitar duplicados/solapes duros dentro del mismo día
                    overlapping = (db.query(AvailabilityBlock)
                                      .filter(AvailabilityBlock.TherapistUserId==uid,
                                              AvailabilityBlock.Weekday==weekday,
                                              AvailabilityBlock.IsActive==True)
                                      .all())
                    def overlaps(a1,a2,b1,b2):  # [a1,a2) vs [b1,b2)
                            return a1 < b2 and b1 < a2
                    if any(overlaps(start_t,end_t, blk.StartTime, blk.EndTime) for blk in overlapping):
                           flash("Se solapa con otro bloque activo.", "warning")
                           return redirect(url_for("therapist_availability", uid=uid))
                         
                    db.add(AvailabilityBlock(TherapistUserId=uid, Weekday=weekday,
                                                  StartTime=start_t, EndTime=end_t,
                                                  IsActive=True))
                    db.commit()
                    flash("Bloque agregado.", "success")
                    return redirect(url_for("therapist_availability", uid=uid))
                             

            
            blocks = (db.query(AvailabilityBlock)
                     .filter(AvailabilityBlock.TherapistUserId==uid)
                     .order_by(AvailabilityBlock.Weekday, AvailabilityBlock.StartTime)
                     .all())
        return render_template("therapist_availability.html", therapist=u, blocks=blocks, WEEK_LABELS=WEEK_LABELS)
    
    @app.post("/therapists/<int:uid>/availability/<int:bid>/toggle")
    def therapist_availability_toggle(uid:int, bid:int):
        with SessionLocal() as db:
            blk = db.get(AvailabilityBlock, bid)
            if not blk or blk.TherapistUserId != uid:
                flash("Bloque no encontrado.", "warning")
            else:
                 blk.IsActive = not bool(blk.IsActive)
                 db.commit()
                 flash("Bloque actualizado.", "success")
        return redirect(url_for("therapist_availability", uid=uid))
    
 
    @app.post("/therapists/<int:uid>/availability/<int:bid>/delete")
    def therapist_availability_delete(uid:int, bid:int):
        with SessionLocal() as db:
            blk = db.get(AvailabilityBlock, bid)
            if not blk or blk.TherapistUserId != uid:
                flash("Bloque no encontrado.", "warning")
            else:
                db.delete(blk)
                db.commit()
                flash("Bloque eliminado.", "success")
        return redirect(url_for("therapist_availability", uid=uid))
    
    
    @app.get("/sessions")
    def sessions_list():
        with SessionLocal() as db:
            rows = (db.query(PgSession, User)
                  .join(User, PgSession.TherapistUserId==User.UserId)
                  .order_by(PgSession.ScheduledAt.desc())
                  .limit(200)
                  .all())
        return render_template("sessions_list.html", sessions=rows)
    
    @app.route("/sessions/new", methods=["GET","POST"])
    def sessions_new():
        with SessionLocal() as db:
            therapists = db.query(User).filter(User.Role=="therapist").order_by(User.LastName, User.FirstName).all()

            if request.method == "POST":
               try:
                   tid = int(request.form.get("TherapistUserId"))
                   date_str = request.form.get("Date")        # YYYY-MM-DD
                   time_str = request.form.get("StartTime")   # HH:MM
                   dur = int(request.form.get("DurationMin"))
                   goal = request.form.get("GoalSummary","").strip() or None
                   notes= request.form.get("Notes","").strip() or None

                   y,m,d = map(int, date_str.split("-"))
                   hh,mm = map(int, time_str.split(":"))
                   start_dt = datetime(y,m,d,hh,mm)
                   end_dt = start_dt + timedelta(minutes=dur)
 
                   # 1) verifica disponibilidad (día y rango dentro de algún bloque activo)
                   weekday = start_dt.weekday()  # 0=Lun..6=Dom
                   blocks = (db.query(AvailabilityBlock)
                              .filter(AvailabilityBlock.TherapistUserId==tid,
                                      AvailabilityBlock.Weekday==weekday,
                                      AvailabilityBlock.IsActive==True)
                              .all())
                   def within_block(dt_start, dt_end, blk):
                       s = blk.StartTime; e = blk.EndTime
                       return (dt_start.time() >= s) and (dt_end.time() <= e)
                  
                   if not any(within_block(start_dt, end_dt, b) for b in blocks):
                       flash("Fuera de disponibilidad del terapeuta.", "danger")
                       return redirect(url_for("sessions_new"))
                
                   # 2) evita solapes con otras sesiones del mismo terapeuta en ese día
                   clash = (db.query(PgSession)
                             .filter(PgSession.TherapistUserId==tid,
                                      PgSession.ScheduledAt < end_dt,
                                      (PgSession.ScheduledAt + (PgSession.DurationMin*60)) > start_dt)  # aprox, no soporta suma; lo validamos en Python abajo
                              .all())
                
                   # ajuste: validar solape en Python porque la suma SQL no es directa
                   def overlaps(a1,a2,b1,b2):
                       return a1 < b2 and b1 < a2
                   overlap_py = False
                   for s in clash:
                       other_Start = s.ScheduledAt
                       other_end = s.ScheduledAt + timedelta(minutes=s.DurationMin)
                       if overlaps(start_dt, end_dt, other_Start, other_end):
                           overlap_py = True
                           break
                   if overlap_py:
                       flash("conflicto con otra sesion del terapeuta." , "warning")
                       return redirect(url_for("sessions_new"))
                   
                   
                   end_dt = start_dt + timedelta(minutes=dur)
                   
                   if start_dt.time() < BUSINESS_START or end_dt.time() > BUSINESS_END:
                       flash("La sesión debe quedar entre 09:00 y 18:00.", "danger")
                       return redirect(url_for("sessions_new"))
                   
                   new_s = PgSession(
                       TherapistUserId=tid,
                       ScheduleAt=start_dt,
                       DurationMin=dur,
                       GoalSummary=goal,
                       Notes=notes,
                       CreatedByUserId=tid, # luego haremos un login y esto usara el usuario autenticado
                       CreatedAt=datetime.utcnow(),                   
                   )
                   db.add(new_s)
                   db.commit()
                   flash("Sesion Creada.", "Success")
                   return redirect(url_for("sessions_list"))
               except Exception:
                   flash("Datos invalidos." , "Danger")
                   return redirect(url_for(sessions_new))
        return render_template("session_form.html", therapists=therapists)
            


    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)


print("DATABASE_URL ->", os.getenv("DATABASE_URL"))
