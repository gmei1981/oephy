function [dtc_delay_out,dtc_code] = dtc(dtc_in,cfg)

% DTC模型
dtc_delay = cfg.dtc_delay + cfg.dtc_inl;
dtc_code = round(dtc_in+1);
if dtc_code<=1
    dtc_code=1;
end
if dtc_code>2^cfg.dtc_width
    dtc_code = 2^cfg.dtc_width;
end
dtc_delay_out = dtc_delay(dtc_code) + cfg.dtc_ofst;
end

