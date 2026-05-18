'use client'

import { Bed, Users, Stethoscope, AlertCircle, Activity, Cpu } from 'lucide-react'
import { MetricCard, CapacityBar, Panel } from '@/components/shared/MetricCard'
import type { HospitalSnapshot } from '@/types'

interface Props {
  snapshot: HospitalSnapshot
}

export function HospitalOverviewCards({ snapshot }: Props) {
  const icuPct = (snapshot.icu_occupancy / snapshot.icu_total_beds) * 100
  const wardPct = (snapshot.regular_bed_occupancy / snapshot.regular_total_beds) * 100

  const icuVariant = icuPct >= 90 ? 'critical' : icuPct >= 75 ? 'warn' : 'ok'
  const wardVariant = wardPct >= 90 ? 'critical' : wardPct >= 75 ? 'warn' : 'ok'
  const drVariant = snapshot.doctor_workload >= 0.95 ? 'critical' : snapshot.doctor_workload >= 0.80 ? 'warn' : 'ok'
  const queueVariant = snapshot.emergency_queue_length >= 10 ? 'critical' : snapshot.emergency_queue_length >= 5 ? 'warn' : 'ok'

  return (
    <div className="space-y-4">
      {/* Top KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
        <MetricCard
          label="ICU Beds"
          value={`${snapshot.icu_occupancy}/${snapshot.icu_total_beds}`}
          sub={`${snapshot.icu_available_beds} available`}
          variant={icuVariant}
          icon={<Bed className="w-4 h-4" />}
        />
        <MetricCard
          label="Ward Beds"
          value={`${snapshot.regular_bed_occupancy}/${snapshot.regular_total_beds}`}
          sub={`${snapshot.regular_available_beds} available`}
          variant={wardVariant}
          icon={<Bed className="w-4 h-4" />}
        />
        <MetricCard
          label="Active Patients"
          value={snapshot.active_patient_count}
          sub={`${snapshot.discharged_count} discharged`}
          variant="default"
          icon={<Users className="w-4 h-4" />}
        />
        <MetricCard
          label="Emergency Queue"
          value={snapshot.emergency_queue_length}
          sub="awaiting triage"
          variant={queueVariant}
          icon={<AlertCircle className="w-4 h-4" />}
        />
        <MetricCard
          label="Throughput"
          value={snapshot.patient_throughput}
          sub="patients processed"
          variant="default"
          trend="up"
          trendValue={`step ${snapshot.step_number}`}
          icon={<Activity className="w-4 h-4" />}
        />
        <MetricCard
          label="Equipment Util."
          value={`${(snapshot.equipment_utilization * 100).toFixed(0)}%`}
          sub={`${snapshot.deceased_count} sim. deaths`}
          variant={snapshot.equipment_utilization >= 0.90 ? 'critical' : snapshot.equipment_utilization >= 0.75 ? 'warn' : 'default'}
          icon={<Cpu className="w-4 h-4" />}
        />
      </div>

      {/* Capacity bars */}
      <Panel className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <Bed className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
              Bed Capacity
            </span>
          </div>
          <CapacityBar label="ICU" value={snapshot.icu_occupancy} max={snapshot.icu_total_beds} />
          <CapacityBar label="Regular Ward" value={snapshot.regular_bed_occupancy} max={snapshot.regular_total_beds} />
        </div>
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <Stethoscope className="w-3.5 h-3.5 text-text-muted" />
            <span className="text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
              Staff Workload
            </span>
          </div>
          <CapacityBar label="Doctors" value={Math.round(snapshot.doctor_workload * 100)} max={100} unit="%" />
          <CapacityBar label="Nurses" value={Math.round(snapshot.nurse_workload * 100)} max={100} unit="%" />
        </div>
      </Panel>

      {/* Simulation status bar */}
      <div className="flex items-center gap-6 px-4 py-2.5 bg-surface-3 rounded-lg border border-surface-border text-xs text-text-muted font-mono">
        <span>
          <span className="text-text-secondary font-semibold">SIM TIME</span>{' '}
          {Math.floor(snapshot.simulation_time / 60)}h {snapshot.simulation_time % 60}m
        </span>
        <span className="text-surface-border">|</span>
        <span>
          <span className="text-text-secondary font-semibold">STEP</span> {snapshot.step_number}
        </span>
        <span className="text-surface-border">|</span>
        <span>
          <span className={snapshot.status === 'ACTIVE' ? 'text-status-ok' : 'text-text-muted'}>
            ● {snapshot.status}
          </span>
        </span>
        <span className="text-surface-border">|</span>
        <span>
          <span className="text-text-secondary font-semibold">MORTALITY</span>{' '}
          {snapshot.discharged_count + snapshot.deceased_count > 0
            ? ((snapshot.deceased_count / (snapshot.discharged_count + snapshot.deceased_count)) * 100).toFixed(1)
            : '0.0'}%
        </span>
        <span className="text-surface-border">|</span>
        <span>
          <span className="text-text-secondary font-semibold">DR WORKLOAD</span>{' '}
          {(snapshot.doctor_workload * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  )
}
