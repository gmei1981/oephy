function [tbl, inl_rms, dnl_rms] = dtc_inl_table(n_code, inl_lsb, dnl_lsb, corr_len)
% dtc_inl_table — per-code DTC INL/DNL table (spec: INL 2 LSB, DNL 1 LSB).
%
%   INL: smoothed random transfer-curve deviation, RMS = inl_lsb, correlation
%        length ~corr_len codes (systematic curvature of the delay line).
%   DNL: NON-accumulating per-code mismatch, scaled so the realized step DNL
%        of the final table (diff of smooth+iid) has RMS = dnl_lsb.
%        (Mismatch-type DNL on purpose: integrating iid DNL over 1024 codes
%        gives a random-walk INL ~ sqrt(n/12)*DNL ~ 9x DNL, which would break
%        the 2 LSB INL spec — real INL 2 LSB + DNL 1 LSB implies the DNL is
%        mostly cell mismatch, not the source of the INL.)
%
%   tbl is in LSB units; caller multiplies by dtc_lsb_cycles to get cycles.
%   Table is drawn from the current rng state (top_adpll seeds it per run).

w = conv(randn(n_code+2*corr_len,1), ones(corr_len+1,1)/(corr_len+1));
inl_s = w(corr_len+1:corr_len+n_code);        % skip filter ramp-in/out edges
inl_s = inl_s - mean(inl_s);
inl_s = inl_s/std(inl_s)*inl_lsb;

dnl_s = [0; diff(inl_s)];                     % step DNL of the smooth part
sig_mm = sqrt(max(dnl_lsb^2 - var(dnl_s), 0)/2);   % each step differs by 2 draws
tbl = inl_s + sig_mm*randn(n_code,1);

inl_rms = std(tbl);                           % realized INL  (~inl_lsb)
dnl_rms = std([0; diff(tbl)]);                % realized DNL  (=dnl_lsb by construction)
end
