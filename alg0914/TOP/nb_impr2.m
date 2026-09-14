% nb_impr2.m — 提升场景补充校准 (2026-09-14)
%   (a) synth 1/256 TDC solo: 校验合成式 TDC 与真实量化器的标度
%       (real 1/256 = 148.8fs; 若 synth256 ≈ 70 则真实量化器有 2x 额外内容)
%   (b) dsmq LUT 残差 0.05LSB: DSM 泄漏还能压多少 (0.2LSB 残差时 62.6fs)
top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));
cfg0 = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fref = cfg0.fref; fout = cfg0.adpll_fcw/2^35*fref; N = round(cfg0.n_cycles);

ideal = struct('tdc_ideal',1,'dsm_fb_ideal',1,'tdc_inl_en',0, ...
    'dtc_inl_lsb',0,'dtc_dnl_lsb',0,'dtc_pn_floor_dbc',-300, ...
    'dco_pn_l1m_dbc',-300,'dco_pn_floor_dbc',-300,'dco_pn_rms_fs',0, ...
    'dco_pn_spec_f_hz','','dco_pn_spec_dbc','', ...
    'dco_glitch_fs_per_code',0,'ref_jitter_fs',0);
dsm_real = struct('dsm_fb_ideal',0,'dtc_inl_lsb',2,'dtc_dnl_lsb',1);
runs = { ...
  'tdcq_synth256', as(ideal,'tdc_synth_lsb_cyc',1/256,'tdc_synth_inl_lsb',0,'seed',7); ...
  'dsmqLUT005_s7', as(as(as(merge(ideal,dsm_real), ...
      struct('dtc_inl_lut_calib_en',1,'dtc_inl_lut_res_lsb',0.05)), ...
      'tdc_synth_lsb_cyc',1/512,'tdc_synth_inl_lsb',0.25),'seed',7)};
for k = 1:size(runs,1)
    key = runs{k,1}; odir = ['nb_' key];
    fprintf('===== impr2 %d/2 : %s =====\n', k, key);
    R = top_adpll('default', as(runs{k,2},'outdir_name',odir));
    e = detrend(R.phi_abs_err(165000:N),1);
    [fk,Lk] = psd_phe(e,fref);
    sig = sqrt(2*trapz(fk(2:end),10.^(Lk(2:end)/10)))/(2*pi*fout)*1e15;
    fprintf('%16s : sigma_t = %.1f fs\n', key, sig);
end
fprintf('done\n');

function s = as(s,varargin)
q = 1;
while q <= numel(varargin)
    if isstruct(varargin{q})
        f = fieldnames(varargin{q});
        for j = 1:numel(f), s.(f{j}) = varargin{q}.(f{j}); end
        q = q + 1;
    else
        s.(varargin{q}) = varargin{q+1};
        q = q + 2;
    end
end
end
function s = merge(a,b)
s = a;
f = fieldnames(b);
for q = 1:numel(f), s.(f{q}) = b.(f{q}); end
end
