import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import axios from 'axios'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './App.css'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api' })
const WS = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
api.interceptors.request.use(c => {
  const t = localStorage.getItem('token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})
api.interceptors.response.use(r => r, e => {
  if (e.response?.status === 401 && !e.config.url.includes('/auth/login')) {
    localStorage.removeItem('token')
    window.dispatchEvent(new Event('session-expired'))
  }
  return Promise.reject(e)
})

const Ctx = createContext()
const useApp = () => useContext(Ctx)
const errText = e => {
  const d = e.response?.data?.detail
  return Array.isArray(d) ? d.map(x => `${x.loc?.slice(-1)[0]}: ${x.msg}`).join(', ') : d || e.message
}
const COLORS = ['#1f4d3a', '#e2573b', '#d9a441', '#1c2321', '#6fa58a', '#b8a77f']
const MGR = ['ADMIN', 'HR', 'MANAGER']
const HR = ['ADMIN', 'HR']
const money = n => '₹' + Math.round(n || 0).toLocaleString('en-IN')
const when = s => (s ? new Date(s + 'Z').toLocaleString() : '')

function useGet(url, deps = []) {
  const { tick } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const load = useCallback(() => {
    if (!url) return
    api.get(url).then(r => { setData(r.data); setError(null) }).catch(e => setError(errText(e)))
  }, [url])
  useEffect(load, [load, tick, ...deps])
  return [data, load, error]
}

async function download(url, name) {
  const r = await api.get(url, { responseType: 'blob' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(r.data)
  a.download = name
  a.click()
}

function useAct() {
  const { toast } = useApp()
  return async (fn, ok) => {
    try {
      const r = await fn()
      if (ok) toast(ok)
      return r
    } catch (e) {
      toast(errText(e), 'err')
    }
  }
}

const Chip = ({ v }) => <span className={`chip ${v}`}>{v}</span>
const Card = ({ title, children, className = '' }) => <div className={`card ${className}`}>{title && <h3 className="serif font-bold">{title}</h3>}{children}</div>
const Stat = ({ label, value }) => <div className="card stat"><b>{value ?? '–'}</b><span>{label}</span></div>
const Loading = ({ error }) => <div className="empty">{error || 'Loading…'}</div>
const Field = ({ label, children }) => <div><label className="lbl">{label}</label>{children}</div>

function Table({ cols, rows, empty = 'Nothing here yet' }) {
  if (!rows) return <Loading />
  if (!rows.length) return <div className="empty">{empty}</div>
  return (
    <div className="overflow-x-auto">
      <table className="tbl">
        <thead><tr>{cols.map(c => <th key={c[0]}>{c[0]}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={r.id ?? i}>{cols.map(c => <td key={c[0]}>{c[1](r)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

function Modal({ title, onClose, children }) {
  return (
    <div className="modal" onClick={onClose}>
      <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between mb-3"><h2 className="serif text-xl font-bold">{title}</h2><button className="btn sm" onClick={onClose}>Close</button></div>
        {children}
      </div>
    </div>
  )
}

function Auth({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [f, setF] = useState({ name: '', email: '', password: '', token: '' })
  const act = useAct()
  const { toast } = useApp()
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const submit = async e => {
    e.preventDefault()
    if (mode === 'login') {
      const r = await act(() => api.post('/auth/login', { email: f.email, password: f.password }))
      if (r) { localStorage.setItem('token', r.data.access_token); onLogin(r.data.user) }
    } else if (mode === 'register') {
      if (await act(() => api.post('/auth/register', { name: f.name, email: f.email, password: f.password }), 'Account created, please sign in')) setMode('login')
    } else if (mode === 'forgot') {
      const r = await act(() => api.post('/auth/forgot-password', { email: f.email }))
      if (r) { toast(r.data.message); if (r.data.reset_token) { setF({ ...f, token: r.data.reset_token }); setMode('reset') } }
    } else if (await act(() => api.post('/auth/reset-password', { token: f.token, password: f.password }), 'Password updated')) setMode('login')
  }
  return (
    <div className="min-h-screen grid md:grid-cols-2">
      <div className="hidden md:flex flex-col justify-end p-12" style={{ background: 'var(--forest)', color: '#fff' }}>
        <h1 className="text-6xl font-extrabold leading-none">Know who is about to leave, <span style={{ color: 'var(--gold)' }}>before they do.</span></h1>
        <p className="mt-6 max-w-md opacity-80">WorkForce AI Pro joins HR operations with an attrition prediction engine, live risk alerts and guided retention workflows.</p>
      </div>
      <div className="grid place-items-center p-6">
        <form onSubmit={submit} className="card w-full max-w-sm space-y-3">
          <h2 className="serif text-2xl font-bold">{{ login: 'Sign in', register: 'Create account', forgot: 'Forgot password', reset: 'Reset password' }[mode]}</h2>
          {mode === 'register' && <Field label="Name"><input className="in" value={f.name} onChange={set('name')} required minLength={2} /></Field>}
          {mode !== 'reset' && <Field label="Email"><input className="in" type="email" value={f.email} onChange={set('email')} required /></Field>}
          {mode === 'reset' && <Field label="Reset token"><input className="in" value={f.token} onChange={set('token')} required /></Field>}
          {mode !== 'forgot' && <Field label={mode === 'reset' ? 'New password' : 'Password'}><input className="in" type="password" value={f.password} onChange={set('password')} required minLength={8} /></Field>}
          <button className="btn solid w-full">{mode === 'forgot' ? 'Get reset token' : 'Continue'}</button>
          <div className="flex justify-between text-sm">
            {mode === 'login' ? <><a href="#" onClick={() => setMode('register')}>Register</a><a href="#" onClick={() => setMode('forgot')}>Forgot password?</a></> : <a href="#" onClick={() => setMode('login')}>Back to sign in</a>}
          </div>
          {mode === 'login' && <p className="text-xs" style={{ color: 'var(--muted)' }}>Demo: admin@workforce.ai / Admin@123 · hr@workforce.ai / Hr@12345 · manager@workforce.ai / Manager@123 · employee@workforce.ai / Employee@123</p>}
        </form>
      </div>
    </div>
  )
}

function Dashboard() {
  const [d, , err] = useGet('/dashboard')
  const [feed] = useGet('/ai/feed')
  if (!d) return <Loading error={err} />
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Active employees" value={d.active} /><Stat label="Present today" value={d.present_today} />
        <Stat label="Pending leaves" value={d.pending_leaves} /><Stat label={`Payroll ${d.payroll_month}`} value={money(d.payroll_total)} />
        <Stat label="Average salary" value={money(d.avg_salary)} /><Stat label="Left the company" value={d.left} />
        <Stat label="High-risk employees" value={d.risk.find(r => r.name === 'HIGH')?.value} /><Stat label="Open interventions" value={d.open_interventions} />
      </div>
      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Headcount by department" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={240}><BarChart data={d.by_department}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" fontSize={11} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="count" fill="#1f4d3a" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer>
        </Card>
        <Card title="Attrition risk mix">
          <ResponsiveContainer width="100%" height={240}><PieChart><Pie data={d.risk} dataKey="value" nameKey="name" innerRadius={48} outerRadius={85} label>{d.risk.map((r, i) => <Cell key={r.name} fill={['#e2573b', '#d9a441', '#1f4d3a'][i]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer>
        </Card>
      </div>
      <Card title="Live workforce feed">
        {feed?.length ? feed.slice(0, 10).map((x, i) => <div key={i} className="flex gap-3 py-1 text-sm border-b border-dashed"><Chip v={x.type === 'RISK' ? 'HIGH' : 'LOW'} /><span className="flex-1">{x.text}</span><span style={{ color: 'var(--muted)' }}>{when(x.at)}</span></div>) : <div className="empty">No activity yet</div>}
      </Card>
    </div>
  )
}

const EMPTY = { name: '', email: '', phone: '', title: 'Staff', department_id: '', salary: 50000, status: 'ACTIVE', shift: 'Morning', age: 30, tenure: 1, satisfaction: 3, overtime: 0, performance: 3, absences: 0, promo_gap: 0 }
const NUM = ['department_id', 'salary', 'age', 'tenure', 'satisfaction', 'overtime', 'performance', 'absences', 'promo_gap']

function Employees() {
  const { user } = useApp()
  const act = useAct()
  const [flt, setFlt] = useState({ q: '', department_id: '', risk: '', status: '' })
  const qs = new URLSearchParams(Object.entries(flt).filter(([, v]) => v)).toString()
  const [res, reload, err] = useGet('/employees?' + qs + '&size=100', [qs])
  const [depts] = useGet('/departments')
  const [form, setForm] = useState(null)
  const canEdit = HR.includes(user.role)
  const save = async e => {
    e.preventDefault()
    const body = { ...form }
    NUM.forEach(k => { body[k] = body[k] === '' ? null : Number(body[k]) })
    const call = form.id ? () => api.put(`/employees/${form.id}`, body) : () => api.post('/employees', body)
    if (await act(call, 'Employee saved')) { setForm(null); reload() }
  }
  const remove = async r => { if (confirm(`Delete ${r.name}?`) && await act(() => api.delete(`/employees/${r.id}`), 'Employee deleted')) reload() }
  const f = k => ({ className: 'in', value: form[k] ?? '', onChange: e => setForm({ ...form, [k]: e.target.value }) })
  return (
    <Card>
      <div className="flex flex-wrap gap-2 mb-3 items-end">
        <div className="flex-1 min-w-48"><label className="lbl">Search</label><input className="in" placeholder="Name, email or title" value={flt.q} onChange={e => setFlt({ ...flt, q: e.target.value })} /></div>
        <div><label className="lbl">Department</label><select className="in" value={flt.department_id} onChange={e => setFlt({ ...flt, department_id: e.target.value })}><option value="">All</option>{depts?.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
        <div><label className="lbl">Risk</label><select className="in" value={flt.risk} onChange={e => setFlt({ ...flt, risk: e.target.value })}><option value="">All</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></div>
        <div><label className="lbl">Status</label><select className="in" value={flt.status} onChange={e => setFlt({ ...flt, status: e.target.value })}><option value="">All</option><option>ACTIVE</option><option>LEFT</option></select></div>
        {canEdit && <button className="btn solid" onClick={() => setForm(EMPTY)}>+ Add employee</button>}
      </div>
      {!res ? <Loading error={err} /> : <>
        <p className="text-xs mb-2" style={{ color: 'var(--muted)' }}>{res.total} employees</p>
        <Table rows={res.items} empty="No employees match these filters" cols={[
          ['Name', r => <><b>{r.name}</b><div className="text-xs" style={{ color: 'var(--muted)' }}>{r.email}</div></>],
          ['Department', r => r.department || '–'], ['Title', r => r.title], ['Salary', r => money(r.salary)], ['Shift', r => r.shift],
          ['Status', r => <Chip v={r.status} />], ['Risk', r => r.risk != null && r.status === 'ACTIVE' ? <span className="whitespace-nowrap"><Chip v={r.risk >= 70 ? 'HIGH' : r.risk >= 40 ? 'MEDIUM' : 'LOW'} /> {r.risk}%</span> : '–'],
          ['', r => canEdit && <span className="flex gap-1"><button className="btn sm" onClick={() => setForm({ ...r })}>Edit</button><button className="btn sm warn" onClick={() => remove(r)}>Delete</button></span>]]} />
      </>}
      {form && (
        <Modal title={form.id ? 'Edit employee' : 'New employee'} onClose={() => setForm(null)}>
          <form onSubmit={save} className="grid grid-cols-2 gap-3">
            <Field label="Name"><input {...f('name')} required /></Field><Field label="Email"><input {...f('email')} type="email" required /></Field>
            <Field label="Phone"><input {...f('phone')} /></Field><Field label="Job title"><input {...f('title')} /></Field>
            <Field label="Department"><select {...f('department_id')}><option value="">None</option>{depts?.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
            <Field label="Annual salary"><input {...f('salary')} type="number" min="1" required /></Field>
            <Field label="Shift"><select {...f('shift')}><option>Morning</option><option>Evening</option><option>Night</option></select></Field>
            <Field label="Status"><select {...f('status')}><option>ACTIVE</option><option>LEFT</option></select></Field>
            <Field label="Age"><input {...f('age')} type="number" min="18" max="70" /></Field><Field label="Tenure (years)"><input {...f('tenure')} type="number" step="0.1" min="0" /></Field>
            <Field label="Satisfaction (1-4)"><input {...f('satisfaction')} type="number" min="1" max="4" /></Field><Field label="Overtime hrs/month"><input {...f('overtime')} type="number" min="0" /></Field>
            <Field label="Performance (1-5)"><input {...f('performance')} type="number" min="1" max="5" /></Field><Field label="Absences"><input {...f('absences')} type="number" min="0" /></Field>
            <Field label="Years since promotion"><input {...f('promo_gap')} type="number" step="0.1" min="0" /></Field>
            <div className="col-span-2"><button className="btn solid">Save and re-run prediction</button></div>
          </form>
        </Modal>)}
    </Card>
  )
}

function Departments() {
  const { user } = useApp()
  const act = useAct()
  const [rows, reload] = useGet('/departments/stats')
  const [f, setF] = useState({ name: '', description: '' })
  const add = async e => { e.preventDefault(); if (await act(() => api.post('/departments', f), 'Department added')) { setF({ name: '', description: '' }); reload() } }
  const del = async r => { if (await act(() => api.delete(`/departments/${r.id}`), 'Department removed')) reload() }
  return (
    <div className="space-y-4">
      {HR.includes(user.role) && <Card title="Add department"><form onSubmit={add} className="flex gap-3 items-end"><Field label="Name"><input className="in" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} required /></Field><div className="flex-1"><Field label="Description"><input className="in" value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></Field></div><button className="btn solid">Add</button></form></Card>}
      <Card title="Department statistics"><Table rows={rows} cols={[['Department', r => <b>{r.name}</b>], ['Headcount', r => r.headcount], ['Avg salary', r => money(r.avg_salary)], ['Avg overtime', r => r.avg_overtime + ' h'], ['Avg risk', r => r.avg_risk + '%'], ['', r => HR.includes(user.role) && <button className="btn sm warn" onClick={() => del(r)}>Delete</button>]]} /></Card>
    </div>
  )
}

function Attendance() {
  const { user } = useApp()
  const act = useAct()
  const [rows, reload] = useGet('/attendance')
  const [hrs, setHrs] = useState('')
  const [emps] = useGet(MGR.includes(user.role) ? '/employees?size=100&status=ACTIVE' : null)
  const [eid, setEid] = useState('')
  const body = { employee_id: eid ? Number(eid) : null }
  const inn = async () => { if (await act(() => api.post('/attendance/check-in', body), 'Checked in')) reload() }
  const out = async () => {
    if (await act(() => api.post('/attendance/check-out' + (hrs ? `?simulate_hours=${hrs}` : ''), body), 'Checked out, risk score refreshed')) reload()
  }
  return (
    <div className="space-y-4">
      <Card title="Check-in / Check-out">
        <div className="flex flex-wrap gap-3 items-end">
          {emps && <Field label="Employee"><select className="in" value={eid} onChange={e => setEid(e.target.value)}><option value="">My profile</option>{emps.items.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></Field>}
          <button className="btn solid" onClick={inn}>Check in</button>
          <Field label="Demo: simulate hours worked"><input className="in" type="number" step="0.5" placeholder="e.g. 14" value={hrs} onChange={e => setHrs(e.target.value)} /></Field>
          <button className="btn warn" onClick={out}>Check out</button>
        </div>
        <p className="text-xs mt-2" style={{ color: 'var(--muted)' }}>Hours above 8 count as overtime and feed the attrition model, which re-scores the employee on every check-out.</p>
      </Card>
      <Card title="Attendance report"><Table rows={rows} cols={[['Date', r => r.day], ['Employee', r => r.employee], ['In', r => r.check_in?.slice(11, 16)], ['Out', r => r.check_out?.slice(11, 16) || 'open'], ['Hours', r => r.hours], ['Overtime', r => r.overtime]]} /></Card>
    </div>
  )
}

function Leaves() {
  const { user } = useApp()
  const act = useAct()
  const [rows, reload] = useGet('/leaves')
  const [bal] = useGet('/leaves/balance')
  const [rep] = useGet(MGR.includes(user.role) ? '/leaves/report' : null)
  const [f, setF] = useState({ kind: 'ANNUAL', start: '', end: '', reason: '' })
  const apply = async e => { e.preventDefault(); if (await act(() => api.post('/leaves', f), 'Leave request sent')) reload() }
  const decide = async (r, status) => { if (await act(() => api.put(`/leaves/${r.id}/decision`, { status }), `Leave ${status.toLowerCase()}`)) reload() }
  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-4">{bal && Object.entries(bal).map(([k, v]) => <Stat key={k} label={`${k} leave remaining of ${v.total}`} value={v.remaining} />)}</div>
      <Card title="Apply for leave"><form onSubmit={apply} className="flex flex-wrap gap-3 items-end">
        <Field label="Type"><select className="in" value={f.kind} onChange={e => setF({ ...f, kind: e.target.value })}><option>ANNUAL</option><option>SICK</option><option>CASUAL</option></select></Field>
        <Field label="From"><input className="in" type="date" required value={f.start} onChange={e => setF({ ...f, start: e.target.value })} /></Field>
        <Field label="To"><input className="in" type="date" required value={f.end} onChange={e => setF({ ...f, end: e.target.value })} /></Field>
        <div className="flex-1 min-w-40"><Field label="Reason"><input className="in" value={f.reason} onChange={e => setF({ ...f, reason: e.target.value })} /></Field></div>
        <button className="btn solid">Apply</button></form></Card>
      <Card title="Leave requests"><Table rows={rows} cols={[['Employee', r => r.employee], ['Type', r => r.kind], ['From', r => r.start], ['To', r => r.end], ['Days', r => r.days], ['Reason', r => r.reason], ['Status', r => <Chip v={r.status} />],
        ['', r => MGR.includes(user.role) && r.status === 'PENDING' && <span className="flex gap-1"><button className="btn sm solid" onClick={() => decide(r, 'APPROVED')}>Approve</button><button className="btn sm warn" onClick={() => decide(r, 'REJECTED')}>Reject</button></span>]]} /></Card>
      {rep && <Card title="Leave report"><Table rows={rep.map((r, i) => ({ ...r, id: i }))} cols={[['Type', r => r.kind], ['Status', r => <Chip v={r.status} />], ['Requests', r => r.requests], ['Days', r => r.days]]} /></Card>}
    </div>
  )
}

function Payroll() {
  const { user } = useApp()
  const act = useAct()
  const month = new Date().toISOString().slice(0, 7)
  const [rows, reload, err] = useGet(user.role === 'MANAGER' ? null : '/payroll')
  const [f, setF] = useState({ month, bonus_pct: 0 })
  const gen = async () => { const r = await act(() => api.post('/payroll/generate', { ...f, bonus_pct: Number(f.bonus_pct) })); if (r) reload() }
  if (user.role === 'MANAGER') return <Card><div className="empty">Payroll is restricted to HR and Admin.</div></Card>
  return (
    <div className="space-y-4">
      {HR.includes(user.role) && <Card title="Generate payroll"><div className="flex gap-3 items-end"><Field label="Month"><input className="in" type="month" value={f.month} onChange={e => setF({ ...f, month: e.target.value })} /></Field><Field label="Bonus % of basic"><input className="in" type="number" min="0" max="100" value={f.bonus_pct} onChange={e => setF({ ...f, bonus_pct: e.target.value })} /></Field><button className="btn solid" onClick={gen}>Generate</button></div></Card>}
      <Card title="Salary breakdown">{!rows ? <Loading error={err} /> : <Table rows={rows} cols={[['Month', r => r.month], ['Employee', r => r.employee], ['Basic', r => money(r.basic)], ['Bonus', r => money(r.bonus)], ['Tax', r => money(r.tax)], ['Net pay', r => <b>{money(r.net)}</b>], ['', r => <button className="btn sm" onClick={() => download(`/payroll/${r.id}/payslip`, `payslip-${r.month}.pdf`)}>Payslip PDF</button>]]} />}</Card>
    </div>
  )
}

function Inbox() {
  const { user, tick } = useApp()
  const act = useAct()
  const [n, reloadN] = useGet('/notifications')
  const [users] = useGet('/users')
  const [peer, setPeer] = useState(null)
  const [msgs, setMsgs] = useState([])
  const [text, setText] = useState('')
  useEffect(() => { if (peer) api.get(`/chat/${peer}`).then(r => setMsgs(r.data)) }, [peer, tick])
  const send = async e => { e.preventDefault(); if (!text.trim()) return; if (await act(() => api.post('/chat', { to: peer, body: text }))) { setText(''); api.get(`/chat/${peer}`).then(r => setMsgs(r.data)) } }
  const readAll = async () => { await act(() => api.put('/notifications/read-all')); reloadN() }
  return (
    <div className="grid lg:grid-cols-2 gap-4">
      <Card title={`Notifications${n ? ` (${n.unread} unread)` : ''}`}>
        <button className="btn sm mb-2" onClick={readAll}>Mark all read</button>
        <div className="max-h-[28rem] overflow-y-auto">
          {n?.items.length ? n.items.map(x => <div key={x.id} className="flex gap-2 py-2 border-b border-dashed text-sm" style={{ opacity: x.read ? 0.55 : 1 }}><Chip v={x.priority} /><span className="flex-1">{x.message}<div className="text-xs" style={{ color: 'var(--muted)' }}>{when(x.created_at)}</div></span>{!x.read && <button className="btn sm" onClick={async () => { await api.put(`/notifications/${x.id}/read`); reloadN() }}>Read</button>}</div>) : <div className="empty">You are all caught up</div>}
        </div>
      </Card>
      <Card title="One-to-one chat">
        <select className="in mb-3" value={peer || ''} onChange={e => setPeer(Number(e.target.value) || null)}><option value="">Choose a colleague</option>{users?.filter(u => u.id !== user.id).map(u => <option key={u.id} value={u.id}>{u.name} ({u.role})</option>)}</select>
        <div className="h-72 overflow-y-auto space-y-2 mb-3">{msgs.length ? msgs.map(m => <div key={m.id} className={`bubble ${m.sender_id === user.id ? 'me' : ''}`}>{m.body}<div className="text-[10px] opacity-60">{when(m.created_at)}{m.sender_id === user.id && (m.read ? ' · seen' : ' · sent')}</div></div>) : <div className="empty">{peer ? 'Say hello' : 'Pick someone to start chatting'}</div>}</div>
        {peer && <form onSubmit={send} className="flex gap-2"><input className="in" placeholder="Type a message" value={text} onChange={e => setText(e.target.value)} /><button className="btn solid">Send</button></form>}
      </Card>
    </div>
  )
}

function Documents() {
  const { user } = useApp()
  const act = useAct()
  const [rows, reload] = useGet('/documents')
  const [emps] = useGet(MGR.includes(user.role) ? '/employees?size=100' : null)
  const [eid, setEid] = useState('')
  const [file, setFile] = useState(null)
  const up = async e => {
    e.preventDefault()
    const fd = new FormData()
    fd.append('employee_id', eid || user.employee_id)
    fd.append('file', file)
    if (await act(() => api.post('/documents', fd), 'Document uploaded')) { setFile(null); e.target.reset(); reload() }
  }
  const del = async r => { if (await act(() => api.delete(`/documents/${r.id}`), 'Document deleted')) reload() }
  return (
    <div className="space-y-4">
      <Card title="Upload document"><form onSubmit={up} className="flex flex-wrap gap-3 items-end">
        {emps && <Field label="Employee"><select className="in" required value={eid} onChange={e => setEid(e.target.value)}><option value="">Choose</option>{emps.items.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
        <Field label="File (PDF, PNG, JPG, DOCX, max 5 MB)"><input className="in" type="file" required onChange={e => setFile(e.target.files[0])} /></Field><button className="btn solid">Upload</button></form></Card>
      <Card title="Employee documents"><Table rows={rows} cols={[['File', r => r.filename], ['Employee', r => r.employee], ['Size', r => Math.round(r.size / 1024) + ' KB'], ['Uploaded', r => when(r.created_at)], ['', r => <span className="flex gap-1"><button className="btn sm" onClick={() => download(`/documents/${r.id}/download`, r.filename)}>Download</button><button className="btn sm warn" onClick={() => del(r)}>Delete</button></span>]]} /></Card>
    </div>
  )
}

function AiLab() {
  const act = useAct()
  const [ds, reload] = useGet('/ai/datasets')
  const [file, setFile] = useState(null)
  const [out, setOut] = useState(null)
  const upload = async e => {
    e.preventDefault()
    const fd = new FormData()
    fd.append('file', file)
    const r = await act(() => api.post('/ai/datasets', fd), 'Dataset uploaded')
    if (r) { setOut({ upload: r.data }); reload() }
  }
  const train = async () => { const r = await act(() => api.post('/ai/train'), 'Model retrained'); if (r) { setOut({ train: r.data }); reload() } }
  const predict = async () => { const r = await act(() => api.post('/ai/predict-all'), 'All employees re-scored'); if (r) setOut({ predict: r.data }) }
  return (
    <div className="space-y-4">
      <Card title="1. Upload dataset version">
        <form onSubmit={upload} className="flex flex-wrap gap-3 items-end"><Field label="CSV file"><input className="in" type="file" accept=".csv" required onChange={e => setFile(e.target.files[0])} /></Field><button className="btn solid">Upload</button><button type="button" className="btn" onClick={() => download('/ai/datasets/template', 'dataset-template.csv')}>Download template</button></form>
        {out?.upload && <p className="text-sm mt-3"><b>Version {out.upload.version}:</b> {out.upload.rows_ok} rows added, {out.upload.rows_failed} failed, {out.upload.duplicates} duplicates skipped.{out.upload.failed_rows.length > 0 && <> Failed rows: {out.upload.failed_rows.map(r => `#${r.row} (${r.columns.join(', ')})`).join('; ')}</>}</p>}
      </Card>
      <Card title="2. Train and predict">
        <div className="flex gap-3"><button className="btn solid" onClick={train}>Retrain model</button><button className="btn warn" onClick={predict}>Re-score all employees</button></div>
        {out?.train && <p className="text-sm mt-3">Accuracy: <b>{(out.train.accuracy * 100).toFixed(1)}%</b> on {out.train.rows} rows.</p>}
        {out?.predict && <p className="text-sm mt-3">{out.predict.predicted} employees scored, {out.predict.high_risk} high risk.</p>}
      </Card>
      <Card title="Dataset versions"><Table rows={ds} cols={[['Version', r => 'v' + r.version], ['File', r => r.filename], ['Rows added', r => r.rows_ok], ['Failed', r => r.rows_failed], ['Duplicates', r => r.duplicates], ['Accuracy', r => r.accuracy ? (r.accuracy * 100).toFixed(1) + '%' : '–'], ['Uploaded', r => when(r.created_at)]]} /></Card>
    </div>
  )
}

function Risk() {
  const { user } = useApp()
  const act = useAct()
  const [high, reloadH] = useGet('/ai/risk/high')
  const [logs] = useGet('/ai/risk/logs')
  const [iv, reloadI] = useGet('/ai/interventions')
  const canEdit = HR.includes(user.role)
  const predict = async r => { const x = await act(() => api.post(`/ai/predict/${r.id}`), `${r.name} re-scored`); if (x) reloadH() }
  const update = async (i, body) => { if (await act(() => api.put(`/ai/interventions/${i.id}`, body), 'Intervention updated')) reloadI() }
  return (
    <div className="space-y-4">
      <Card title="High-risk employees"><Table rows={high} empty="No one is above the high-risk threshold" cols={[['Employee', r => <><b>{r.name}</b><div className="text-xs">{r.department} · {r.title}</div></>], ['Risk', r => <><Chip v={r.level} /> {r.risk}%</>], ['Suggested actions', r => <ul className="list-disc ml-4 text-xs">{r.recommendations.map(t => <li key={t}>{t}</li>)}</ul>], ['', r => <button className="btn sm" onClick={() => predict(r)}>Re-score</button>]]} /></Card>
      <Card title="Intervention tracker"><Table rows={iv} cols={[['Employee', r => r.employee], ['Action', r => r.action], ['Status', r => canEdit ? <select className="in" value={r.status} onChange={e => update(r, { status: e.target.value })}><option>OPEN</option><option>IN_PROGRESS</option><option>DONE</option></select> : <Chip v={r.status} />], ['HR notes', r => canEdit ? <input className="in" defaultValue={r.notes || ''} onBlur={e => e.target.value !== (r.notes || '') && update(r, { notes: e.target.value })} placeholder="Follow-up notes" /> : r.notes], ['Opened', r => when(r.created_at)]]} /></Card>
      <Card title="Risk monitoring log"><Table rows={logs} cols={[['When', r => when(r.created_at)], ['Employee', r => r.employee], ['Change', r => r.old_risk != null ? `${r.old_risk}% → ${r.new_risk}%` : `${r.new_risk}%`], ['Event', r => r.message]]} /></Card>
    </div>
  )
}

function Analytics() {
  const [a] = useGet('/ai/analytics')
  const [f] = useGet('/ai/forecast?months=12')
  if (!a || !f) return <Loading />
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Historical turnover" value={a.turnover_pct + '%'} /><Stat label="Predicted yearly exits" value={f.yearly_exit_rate_pct + '%'} />
        <Stat label="Workforce stability" value={<Chip v={f.stability} />} /><Stat label="Model accuracy" value={a.latest_accuracy ? (a.latest_accuracy * 100).toFixed(1) + '%' : '–'} />
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Monthly headcount forecast"><ResponsiveContainer width="100%" height={250}><LineChart data={f.monthly}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" label={{ value: 'months ahead', position: 'insideBottom', offset: -2, fontSize: 11 }} /><YAxis domain={['auto', 'auto']} /><Tooltip /><Line dataKey="headcount" stroke="#1f4d3a" strokeWidth={3} /><Line dataKey="expected_exits" stroke="#e2573b" strokeWidth={2} /></LineChart></ResponsiveContainer></Card>
        <Card title="Department stability score"><ResponsiveContainer width="100%" height={250}><BarChart data={f.departments}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" fontSize={10} /><YAxis domain={[0, 100]} /><Tooltip /><Bar dataKey="stability_score" fill="#1f4d3a" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></Card>
        <Card title="Turnover and risk by department"><ResponsiveContainer width="100%" height={250}><BarChart data={a.departments}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" fontSize={10} /><YAxis /><Tooltip /><Bar dataKey="turnover_pct" name="Turnover %" fill="#d9a441" radius={[6, 6, 0, 0]} /><Bar dataKey="avg_risk" name="Avg risk %" fill="#e2573b" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></Card>
        <Card title="What drives attrition"><ResponsiveContainer width="100%" height={250}><BarChart data={a.drivers} layout="vertical"><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" /><YAxis type="category" dataKey="feature" width={90} fontSize={11} /><Tooltip /><Bar dataKey="weight" fill="#1c2321" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></Card>
      </div>
      {a.trend.length > 1 && <Card title="Average risk trend"><ResponsiveContainer width="100%" height={200}><LineChart data={a.trend}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="day" fontSize={11} /><YAxis /><Tooltip /><Line dataKey="avg_risk" stroke="#e2573b" strokeWidth={3} /></LineChart></ResponsiveContainer></Card>}
      <Card title="Department forecast"><Table rows={f.departments.map((d, i) => ({ ...d, id: i }))} cols={[['Department', r => r.name], ['Headcount', r => r.headcount], ['Stability', r => r.stability_score], ['Expected exits / year', r => r.expected_exits_year]]} /></Card>
    </div>
  )
}

function Reports() {
  const [logs] = useGet('/audit?limit=60')
  const kinds = ['employees', 'attrition', 'payroll', 'attendance']
  return (
    <div className="space-y-4">
      <Card title="Export reports"><div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">{kinds.map(k => <div key={k} className="border-2 border-dashed rounded-xl p-3"><b className="capitalize">{k}</b><div className="flex gap-2 mt-2"><button className="btn sm" onClick={() => download(`/reports/${k}?fmt=xlsx`, `${k}.xlsx`)}>Excel</button><button className="btn sm" onClick={() => download(`/reports/${k}?fmt=pdf`, `${k}.pdf`)}>PDF</button></div></div>)}</div></Card>
      <Card title="Audit log"><Table rows={logs} cols={[['When', r => when(r.created_at)], ['User', r => r.user], ['Action', r => <b>{r.action}</b>], ['Detail', r => r.detail]]} /></Card>
    </div>
  )
}

const NAV = [
  ['dashboard', 'Dashboard', Dashboard, MGR], ['employees', 'Employees', Employees, MGR], ['departments', 'Departments', Departments, MGR],
  ['attendance', 'Attendance', Attendance, null], ['leaves', 'Leave', Leaves, null], ['payroll', 'Payroll', Payroll, ['ADMIN', 'HR', 'EMPLOYEE']],
  ['inbox', 'Inbox & Chat', Inbox, null], ['documents', 'Documents', Documents, null], ['risk', 'Risk Monitor', Risk, MGR],
  ['analytics', 'Analytics & Forecast', Analytics, MGR], ['ailab', 'AI Lab', AiLab, HR], ['reports', 'Reports & Audit', Reports, HR],
]

function Shell() {
  const { user, logout } = useApp()
  const items = NAV.filter(n => !n[3] || n[3].includes(user.role))
  const [page, setPage] = useState(items[0][0])
  const Page = items.find(n => n[0] === page)[2]
  const [n] = useGet('/notifications')
  return (
    <div className="min-h-screen md:flex">
      <aside className="md:w-64 p-4 md:sticky md:top-0 md:h-screen border-r-2 border-[var(--ink)] bg-[var(--card)] flex flex-col">
        <h1 className="text-2xl font-extrabold leading-tight mb-5">WorkForce<br /><span style={{ color: 'var(--coral)' }}>AI Pro</span></h1>
        <nav className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible flex-1">{items.map(i => <button key={i[0]} className={`nav ${page === i[0] ? 'on' : ''}`} onClick={() => setPage(i[0])}>{i[1]}{i[0] === 'inbox' && n?.unread > 0 && <span className="chip HIGH ml-auto">{n.unread}</span>}</button>)}</nav>
        <div className="text-xs mt-4 hidden md:block"><b>{user.name}</b><div style={{ color: 'var(--muted)' }}>{user.role}</div><button className="btn sm mt-2" onClick={logout}>Sign out</button></div>
      </aside>
      <main className="flex-1 p-5 md:p-8 min-w-0">
        <h2 className="text-4xl font-extrabold mb-5">{items.find(i => i[0] === page)[1]}</h2>
        <Page />
      </main>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const [toasts, setToasts] = useState([])
  const [tick, setTick] = useState(0)
  const toast = useCallback((msg, type = '') => {
    const id = Math.random()
    setToasts(t => [...t, { id, msg, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4500)
  }, [])
  const logout = useCallback(() => { localStorage.removeItem('token'); setUser(null) }, [])

  useEffect(() => {
    if (!localStorage.getItem('token')) return setReady(true)
    api.get('/auth/me').then(r => setUser(r.data)).catch(() => {}).finally(() => setReady(true))
    const expired = () => { setUser(null); toast('Session expired, please sign in again', 'err') }
    window.addEventListener('session-expired', expired)
    return () => window.removeEventListener('session-expired', expired)
  }, [toast])

  useEffect(() => {
    if (!user) return
    const ws = new WebSocket(`${WS}?token=${localStorage.getItem('token')}`)
    ws.onmessage = e => {
      const d = JSON.parse(e.data)
      d.notifications?.forEach(n => toast(n.message, n.priority === 'HIGH' || n.priority === 'CRITICAL' ? 'err' : ''))
      setTick(t => t + 1)
    }
    return () => ws.close()
  }, [user, toast])

  if (!ready) return null
  return (
    <Ctx.Provider value={{ user, toast, tick, logout }}>
      {user ? <Shell /> : <Auth onLogin={setUser} />}
      <div className="toast">{toasts.map(t => <div key={t.id} className={t.type}>{t.msg}</div>)}</div>
    </Ctx.Provider>
  )
}
