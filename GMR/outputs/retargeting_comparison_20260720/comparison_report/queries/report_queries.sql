-- average_metrics_sql: Selects the paired macro averages joined to independent physical-validity audits.
SELECT * FROM average_metrics
ORDER BY CASE method
  WHEN 'Direct Mapping' THEN 1
  WHEN 'Basic IK' THEN 2
  WHEN 'GMR' THEN 3
END;

-- normalized_profile_sql: Selects the lower-is-better, per-metric min-max profile used by the average line chart.
SELECT * FROM normalized_profile
ORDER BY metric_order,
  CASE method
    WHEN 'Direct Mapping' THEN 1
    WHEN 'Basic IK' THEN 2
    WHEN 'GMR' THEN 3
  END;

-- per_motion_metrics_sql: Selects all 27 paired motion-method rows in deterministic order.
SELECT * FROM per_motion_metrics
ORDER BY motion,
  CASE method
    WHEN 'Direct Mapping' THEN 1
    WHEN 'Basic IK' THEN 2
    WHEN 'GMR' THEN 3
  END;

-- win_counts_sql: Selects metric-specific motion win counts for the grouped comparison chart.
SELECT * FROM win_counts
ORDER BY metric_order,
  CASE method
    WHEN 'Direct Mapping' THEN 1
    WHEN 'Basic IK' THEN 2
    WHEN 'GMR' THEN 3
  END;

-- direct_collision_sql: Selects the nine-motion Direct Mapping visual-geometry overlap audit.
SELECT * FROM direct_collision_audit ORDER BY motion;
