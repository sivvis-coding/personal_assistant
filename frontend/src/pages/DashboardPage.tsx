import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Grid,
  Skeleton,
  Typography,
} from '@mui/material';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import { useMetricsStore } from '../stores/metricsStore';
import { getDashboardMetrics } from '../api/metrics';

interface MetricCardProps {
  title: string;
  value: number;
  icon: React.ReactNode;
  onClick?: () => void;
  color?: string;
}

/**
 * Render a single metric card.
 */
function MetricCard({ title, value, icon, onClick, color }: MetricCardProps) {
  return (
    <Card>
      <CardActionArea onClick={onClick} disabled={!onClick}>
        <CardContent sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box>
            <Typography color="text.secondary" variant="overline">
              {title}
            </Typography>
            <Typography variant="h3" sx={{ color: color ?? 'text.primary' }}>
              {value}
            </Typography>
          </Box>
          <Box sx={{ color: 'action.active', fontSize: 48 }}>{icon}</Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

/**
 * Render the main dashboard with key metrics.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX dashboard page.
 *
 * Edge cases:
 *   Metrics are loaded from the backend on mount; missing data shows skeletons.
 */
export function DashboardPage() {
  const navigate = useNavigate();
  const { metrics, isLoading, error, setMetrics, setLoading, setError } = useMetricsStore();

  useEffect(() => {
    async function loadMetrics() {
      setLoading(true);
      try {
        const data = await getDashboardMetrics();
        setMetrics(data);
      } catch (caught) {
        setError((caught as Error).message);
      } finally {
        setLoading(false);
      }
    }
    void loadMetrics();
  }, [setMetrics, setLoading, setError]);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Resumen
      </Typography>
      {error ? (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      ) : null}
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          {isLoading || !metrics ? (
            <Skeleton variant="rectangular" height={120} />
          ) : (
            <MetricCard
              title="Tickets abiertos"
              value={metrics.tickets.open}
              icon={<ConfirmationNumberIcon fontSize="inherit" />}
              onClick={() => navigate('/tickets')}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          {isLoading || !metrics ? (
            <Skeleton variant="rectangular" height={120} />
          ) : (
            <MetricCard
              title="Tickets atrasados"
              value={metrics.tickets.overdue}
              icon={<ConfirmationNumberIcon fontSize="inherit" />}
              color="error.main"
              onClick={() => navigate('/tickets')}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          {isLoading || !metrics ? (
            <Skeleton variant="rectangular" height={120} />
          ) : (
            <MetricCard
              title="Tareas pendientes"
              value={metrics.tasks.pending}
              icon={<AssignmentIcon fontSize="inherit" />}
              onClick={() => navigate('/actions')}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          {isLoading || !metrics ? (
            <Skeleton variant="rectangular" height={120} />
          ) : (
            <MetricCard
              title="Acciones por revisar"
              value={metrics.actions.pending_approval}
              icon={<AssignmentTurnedInIcon fontSize="inherit" />}
              color="warning.main"
              onClick={() => navigate('/actions')}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          {isLoading || !metrics ? (
            <Skeleton variant="rectangular" height={120} />
          ) : (
            <MetricCard
              title="Horas esta semana"
              value={metrics.time.week_hours}
              icon={<AccessTimeIcon fontSize="inherit" />}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          {isLoading || !metrics ? (
            <Skeleton variant="rectangular" height={120} />
          ) : (
            <MetricCard
              title="Tareas en sprint"
              value={metrics.tasks.in_sprint}
              icon={<AssignmentIcon fontSize="inherit" />}
            />
          )}
        </Grid>
      </Grid>
    </Box>
  );
}
