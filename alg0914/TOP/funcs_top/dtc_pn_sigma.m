function sig_t = dtc_pn_sigma(l_floor_dbc, fref, fout)
% dtc_pn_sigma — DTC PN-floor spec -> RMS white edge jitter.
%
%   Spec: PN floor L dBc/Hz measured at the DTC output rate fout (100 MHz).
%   One-sided phase PSD S_phi = 2*10^(L/10) rad^2/Hz (L = S_phi/2), white,
%   band-limited to the Nyquist rate of the per-reference-edge sampling
%   (fref/2):  sigma_phi = sqrt(S_phi*fref/2),  sigma_t = sigma_phi/(2*pi*fout).
%   L = -160 dBc/Hz, fref = fout = 100 MHz  ->  159 fs RMS per DTC output edge.

sig_t = sqrt(2*10^(l_floor_dbc/10)*fref/2)/(2*pi*fout);
end
