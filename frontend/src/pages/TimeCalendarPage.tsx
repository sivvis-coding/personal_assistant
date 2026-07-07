import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import { blue } from '@mui/material/colors';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TodayIcon from '@mui/icons-material/Today';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ChatIcon from '@mui/icons-material/Chat';
import { getMonthTime } from '../api/clickup';
import { DayTimeEntryDialog } from '../components/time/DayTimeEntryDialog';
import type { DayTimeSummary, MonthTimeResponse } from '../types/clickup';

const WEEKDAY_LABELS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const MONTH_LABELS = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

// Sequential single-hue scale (light -> dark) for hours logged that day.
// Kept to a few discrete steps rather than a continuous gradient so the
// difference between days is legible at a glance, not just decorative.
function hoursBackground(hours: number): string {
  if (hours <= 0) return 'transparent';
  if (hours < 2) return blue[50];
  if (hours < 4) return blue[100];
  if (hours < 6) return blue[200];
  if (hours < 8) return blue[300];
  return blue[400];
}

function parseLocalDate(isoDate: string): Date {
  const [year, month, day] = isoDate.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function isSameDate(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

// A day "needs attention" only if it's a weekday, already in the past, and has
// no logged hours — weekends and future days are not flagged as missing.
function isMissingWorkday(day: DayTimeSummary, today: Date): boolean {
  const date = parseLocalDate(day.date);
  const isWeekday = date.getDay() >= 1 && date.getDay() <= 5;
  const isPast = date < today;
  return isWeekday && isPast && day.total_hours <= 0;
}

function buildWeeks(days: DayTimeSummary[]): (DayTimeSummary | null)[][] {
  if (days.length === 0) return [];
  const firstWeekday = parseLocalDate(days[0].date).getDay(); // 0=Sun..6=Sat
  const leadingBlanks = firstWeekday === 0 ? 6 : firstWeekday - 1; // Monday-first grid

  const cells: (DayTimeSummary | null)[] = [...Array(leadingBlanks).fill(null), ...days];
  while (cells.length % 7 !== 0) cells.push(null);

  const weeks: (DayTimeSummary | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7));
  }
  return weeks;
}

/**
 * Render a monthly calendar of logged ClickUp hours per day.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX calendar page highlighting days with no logged hours.
 *
 * Edge cases:
 *   Missing ClickUp credentials render mock data from the backend.
 */
export function TimeCalendarPage() {
  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1); // 1-12
  const [report, setReport] = useState<MonthTimeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    silentRefetch().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month]);

  // Re-fetch without toggling the full-page loading state, so it can run quietly
  // in the background (e.g. while the day popup is still open on top) instead of
  // flashing the whole calendar to a spinner.
  async function silentRefetch(): Promise<void> {
    try {
      setReport(await getMonthTime(year, month));
    } catch (caught) {
      setError((caught as Error).message);
    }
  }

  function goToPreviousMonth(): void {
    if (month === 1) {
      setYear((y) => y - 1);
      setMonth(12);
    } else {
      setMonth((m) => m - 1);
    }
  }

  function goToNextMonth(): void {
    if (month === 12) {
      setYear((y) => y + 1);
      setMonth(1);
    } else {
      setMonth((m) => m + 1);
    }
  }

  function goToToday(): void {
    setYear(today.getFullYear());
    setMonth(today.getMonth() + 1);
  }

  const weeks = useMemo(() => buildWeeks(report?.days ?? []), [report]);
  const missingDays = useMemo(
    () => (report?.days ?? []).filter((day) => isMissingWorkday(day, today)),
    [report, today],
  );

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        <Typography variant="h4" sx={{ flexGrow: 1 }}>
          {MONTH_LABELS[month - 1]} {year}
        </Typography>
        <Tooltip title="Mes anterior">
          <IconButton onClick={goToPreviousMonth} size="small">
            <ChevronLeftIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="Ir a hoy">
          <IconButton onClick={goToToday} size="small">
            <TodayIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="Mes siguiente">
          <IconButton onClick={goToNextMonth} size="small">
            <ChevronRightIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {error ? <Typography color="error" sx={{ mb: 2 }}>{error}</Typography> : null}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
          <CircularProgress />
        </Box>
      ) : report ? (
        <>
          <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
            <Chip label={`Total: ${report.total_hours}h`} color="primary" variant="outlined" />
            {missingDays.length > 0 ? (
              <Chip
                icon={<WarningAmberIcon />}
                label={`${missingDays.length} día${missingDays.length !== 1 ? 's' : ''} sin imputar`}
                color="warning"
                variant="outlined"
              />
            ) : (
              <Chip label="Todos los días laborables tienen horas" color="success" variant="outlined" />
            )}
            {report.source === 'mock' ? <Chip label="Datos de ejemplo (sin credenciales ClickUp)" size="small" /> : null}
          </Box>

          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 0.5, mb: 1 }}>
                {WEEKDAY_LABELS.map((label) => (
                  <Typography key={label} variant="caption" color="text.secondary" align="center" sx={{ fontWeight: 600 }}>
                    {label}
                  </Typography>
                ))}
              </Box>

              {weeks.map((week, weekIndex) => (
                <Box key={weekIndex} sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 0.5, mb: 0.5 }}>
                  {week.map((day, dayIndex) => {
                    if (!day) return <Box key={dayIndex} />;
                    const date = parseLocalDate(day.date);
                    const missing = isMissingWorkday(day, today);
                    const isToday = isSameDate(date, today);
                    const taskSummary = day.entries.map((entry) => `${entry.task_name}: ${entry.hours}h`).join('\n');

                    const baseTooltip = day.entries.length > 0 ? taskSummary : missing ? 'Sin imputar' : 'Sin actividad';

                    return (
                      <Tooltip
                        key={day.date}
                        title={`${baseTooltip} — clic para imputar este día`}
                        placement="top"
                      >
                        <Box
                          onClick={() => setSelectedDate(day.date)}
                          sx={{
                            position: 'relative',
                            aspectRatio: '1',
                            minHeight: 56,
                            borderRadius: 1,
                            p: 0.75,
                            bgcolor: hoursBackground(day.total_hours),
                            border: '1px solid',
                            borderColor: missing ? 'warning.main' : isToday ? 'primary.main' : 'divider',
                            borderLeftWidth: missing ? 3 : 1,
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            cursor: 'pointer',
                            transition: 'box-shadow 0.15s, transform 0.15s',
                            '&:hover': {
                              boxShadow: 2,
                              transform: 'scale(1.03)',
                            },
                            '&:hover .day-chat-hint': {
                              opacity: 1,
                            },
                          }}
                        >
                          <Typography variant="caption" sx={{ fontWeight: isToday ? 700 : 400 }}>
                            {date.getDate()}
                          </Typography>
                          {missing ? (
                            <WarningAmberIcon sx={{ position: 'absolute', top: 2, right: 2, fontSize: 14 }} color="warning" />
                          ) : (
                            <ChatIcon
                              className="day-chat-hint"
                              sx={{ position: 'absolute', top: 2, right: 2, fontSize: 14, opacity: 0, color: 'text.disabled' }}
                            />
                          )}
                          {day.total_hours > 0 ? (
                            <Typography variant="caption" sx={{ fontWeight: 600 }}>
                              {day.total_hours}h
                            </Typography>
                          ) : null}
                        </Box>
                      </Tooltip>
                    );
                  })}
                </Box>
              ))}

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2 }}>
                <Typography variant="caption" color="text.secondary">Menos horas</Typography>
                {[0, 1, 3, 5, 7, 8].map((hours) => (
                  <Box
                    key={hours}
                    sx={{ width: 16, height: 16, borderRadius: 0.5, bgcolor: hoursBackground(hours), border: '1px solid', borderColor: 'divider' }}
                  />
                ))}
                <Typography variant="caption" color="text.secondary">Más horas</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 2 }}>
                  <WarningAmberIcon sx={{ fontSize: 14 }} color="warning" />
                  <Typography variant="caption" color="text.secondary">Día laborable sin imputar</Typography>
                </Box>
              </Box>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                Clica un día para abrir el popup de imputación directamente para esa fecha.
              </Typography>
            </CardContent>
          </Card>
        </>
      ) : null}

      <DayTimeEntryDialog
        date={selectedDate}
        onClose={() => {
          setSelectedDate(null);
          void silentRefetch();
        }}
        onActionSettled={() => void silentRefetch()}
      />
    </Box>
  );
}
