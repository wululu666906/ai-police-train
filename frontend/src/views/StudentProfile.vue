<template>
  <div class="student-profile-page space-y-4 pb-20">
    <div class="student-profile-backbar">
      <van-button plain icon="arrow-left" type="primary" @click="goBackToStudents">返回学员账号</van-button>
      <span>学员画像</span>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="bg-white rounded-xl border border-gray-100 shadow-sm py-24 text-center">
      <van-loading color="#1a56db" size="24">正在加载画像数据...</van-loading>
    </div>
    <!-- 错误 -->
    <div v-else-if="pageError" class="bg-white rounded-xl border border-amber-200 px-6 py-16 text-center">
      <van-icon name="warning-o" size="36" class="text-amber-500" />
      <p class="mt-4 text-base font-bold text-amber-800">{{ pageError }}</p>
      <van-button plain type="primary" class="mt-6" @click="fetchProfile">重新加载</van-button>
    </div>

    <template v-else-if="profile">

      <!-- ════════════════════════════════════════
           BLOCK 1  学员信息总览
      ════════════════════════════════════════ -->
      <div class="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-4">
        <!-- 用 grid 强制四列，避免 flex-wrap 导致换行 -->
        <div class="grid gap-4" style="grid-template-columns: 110px 1fr auto auto;">

          <!-- 头像 -->
          <div class="w-[110px] h-[110px] rounded-xl overflow-hidden flex-shrink-0 relative self-center"
               style="background:linear-gradient(155deg,#0f2d6b 0%,#1a4fa0 50%,#2563eb 100%)">
            <div class="absolute inset-0 flex items-center justify-center select-none">
              <span class="text-white text-[38px] font-black" style="text-shadow:0 2px 10px rgba(0,0,0,.4)">
                {{ studentInitials }}
              </span>
            </div>
            <div class="absolute inset-x-0 bottom-0 h-8"
                 style="background:linear-gradient(0deg,rgba(255,255,255,.15) 0%,transparent 100%)"></div>
          </div>

          <!-- 姓名 + 描述 + 标签 -->
          <div class="min-w-0 self-center">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xl font-black text-gray-900 leading-none">{{ profile.student.username }}</span>
              <span class="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-[#1a56db]">
                {{ profile.summary.level || '待积累阶段' }}
              </span>
            </div>
            <div class="flex flex-wrap gap-4 mt-1.5 text-xs text-gray-400">
              <span>学员ID：{{ studentCode }}</span>
              <span>所属单位：{{ primarySceneLabel }}</span>
            </div>
            <p class="mt-2 text-[12px] text-gray-500 leading-[1.75] max-w-[320px]">
              {{ profile.summary.summary_text || '当前仍处于画像积累阶段，系统会根据后续训练记录逐步补齐整体判断与建议。' }}
            </p>
            <div class="flex flex-wrap gap-1.5 mt-2.5">
              <span v-for="tag in traitTags" :key="tag"
                class="inline-flex items-center rounded-md bg-blue-50 border border-blue-100 px-2.5 py-0.5 text-[11px] font-bold text-[#1a56db]"
              >{{ tag }}</span>
            </div>
          </div>

          <!-- 综合能力评分 -->
          <div class="flex flex-col justify-center border-l border-gray-100 pl-5 self-center">
            <div class="text-[11px] text-gray-400 whitespace-nowrap">综合能力评分</div>
            <div class="flex items-baseline gap-1 mt-0.5">
              <span class="text-[52px] font-black leading-none text-[#1a3a6e]">{{ scoreDisplay }}</span>
              <span class="text-[14px] font-bold text-gray-300">/100</span>
            </div>
            <div class="flex items-center gap-1 mt-1.5">
              <span :class="['text-base font-black', scoreDelta >= 0 ? 'text-green-500' : 'text-red-500']">
                {{ scoreDelta >= 0 ? '↑' : '↓' }} {{ Math.abs(scoreDelta) }}
              </span>
            </div>
            <div class="text-[11px] text-gray-400 mt-0.5 whitespace-nowrap">较上月{{ scoreDelta >= 0 ? '提升' : '回落' }}</div>
          </div>

          <!-- 6 格统计（2×3） -->
          <div class="border-l border-gray-100 pl-5 grid grid-cols-2 gap-x-5 gap-y-3 self-center">
            <div v-for="stat in summaryStats" :key="stat.label" class="flex items-center gap-2 w-[92px]">
              <div :class="['w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0', stat.iconBg]">
                <van-icon :name="stat.icon" size="14" :class="stat.iconColor" />
              </div>
              <div>
                <div class="text-[10px] text-gray-400 leading-none whitespace-nowrap">{{ stat.label }}</div>
                <div :class="['text-[12px] font-black mt-0.5 leading-none whitespace-nowrap', stat.valColor]">{{ stat.value }}</div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- ════════════════════════════════════════
           BLOCK 2  能力概览 + 成长趋势（左右各一）
      ════════════════════════════════════════ -->
      <div class="grid grid-cols-2 gap-4">

        <!-- 能力概览 -->
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <div class="text-sm font-black text-gray-800 mb-3">能力概览</div>
          <div class="flex gap-3">

            <!-- 雷达图 -->
            <div class="flex-shrink-0" style="width:200px">
              <svg viewBox="0 0 200 200" width="200" height="200">
                <polygon v-for="lv in [20,40,60,80,100]" :key="`bg${lv}`"
                  :points="radarBgPts(lv)" fill="none" stroke="#e5e7eb" stroke-width="0.8"/>
                <line v-for="(pt,i) in radarAxisPts" :key="`ax${i}`"
                  x1="100" y1="100" :x2="pt.x" :y2="pt.y" stroke="#e5e7eb" stroke-width="0.8"/>
                <polygon :points="radarAvgPts"
                  fill="none" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="3 2.5"/>
                <polygon :points="radarDataPts"
                  fill="rgba(59,130,246,.15)" stroke="#3b82f6" stroke-width="1.8"/>
                <circle v-for="(pt,i) in radarDotList" :key="`rd${i}`"
                  :cx="pt.x" :cy="pt.y" r="2.8" fill="white" stroke="#3b82f6" stroke-width="1.6"/>
                <g v-for="(item,i) in abilityRows" :key="`rl${i}`">
                  <text :x="radarLabelPts[i].x" :y="radarLabelPts[i].y - 5"
                    text-anchor="middle" font-size="8.5" fill="#6b7280" font-family="sans-serif">{{ item.label }}</text>
                  <text :x="radarLabelPts[i].x" :y="radarLabelPts[i].y + 7"
                    text-anchor="middle" font-size="10" font-weight="700" fill="#1e3a5f" font-family="sans-serif">{{ fmt(item.score) }}</text>
                </g>
              </svg>
              <div class="flex items-center gap-4 justify-center mt-0.5">
                <div class="flex items-center gap-1.5">
                  <svg width="16" height="4"><line x1="0" y1="2" x2="16" y2="2" stroke="#3b82f6" stroke-width="2"/></svg>
                  <span class="text-[10px] text-gray-400">本次表现</span>
                </div>
                <div class="flex items-center gap-1.5">
                  <svg width="16" height="4"><line x1="0" y1="2" x2="16" y2="2" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="3 2"/></svg>
                  <span class="text-[10px] text-gray-400">同阶段平均</span>
                </div>
              </div>
            </div>

            <!-- 优势 / 待提升 -->
            <div class="flex-1 min-w-0 flex flex-col justify-between py-1">
              <div>
                <div class="flex items-center gap-1.5 mb-2">
                  <span class="w-2 h-2 rounded-full bg-green-500"></span>
                  <span class="text-xs font-black text-gray-700">优势能力</span>
                </div>
                <div class="space-y-1.5">
                  <div v-for="item in strengths" :key="`g${item.key}`"
                    class="flex items-center justify-between rounded-lg bg-green-50 px-3 py-1.5">
                    <div class="flex items-center gap-1.5">
                      <van-icon name="checked" size="12" class="text-green-500"/>
                      <span class="text-xs font-semibold text-gray-700">{{ item.label }}</span>
                    </div>
                    <span class="text-xs font-black text-green-600">{{ fmt(item.score) }} 分</span>
                  </div>
                  <p v-if="!strengths.length" class="text-xs text-gray-400 px-1">暂无明显优势项</p>
                </div>
              </div>
              <div class="mt-3">
                <div class="flex items-center gap-1.5 mb-2">
                  <span class="w-2 h-2 rounded-full bg-orange-400"></span>
                  <span class="text-xs font-black text-gray-700">待提升能力</span>
                </div>
                <div class="space-y-1.5">
                  <div v-for="item in weaknesses" :key="`w${item.key}`"
                    class="flex items-center justify-between rounded-lg bg-orange-50 px-3 py-1.5">
                    <div class="flex items-center gap-1.5">
                      <van-icon name="warning" size="12" class="text-orange-400"/>
                      <span class="text-xs font-semibold text-gray-700">{{ item.label }}</span>
                    </div>
                    <span class="text-xs font-black text-orange-500">{{ fmt(item.score) }} 分</span>
                  </div>
                  <p v-if="!weaknesses.length" class="text-xs text-gray-400 px-1">暂无待提升项</p>
                </div>
              </div>
              <div class="mt-3 pt-2.5 border-t border-gray-100">
                <span class="text-xs font-bold text-[#1a56db] cursor-pointer hover:underline">查看能力详情 →</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 成长趋势 -->
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <div class="flex items-center justify-between mb-1.5">
            <div class="text-sm font-black text-gray-800">成长趋势</div>
            <button class="flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] text-gray-500 hover:bg-gray-100 transition-colors">
              近30天 <span class="ml-0.5 text-gray-400">▾</span>
            </button>
          </div>
          <div class="text-[11px] text-gray-400 mb-2">综合能力趋势</div>

          <div style="height:150px">
            <svg viewBox="0 0 400 120" class="w-full h-full" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.2"/>
                  <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.01"/>
                </linearGradient>
              </defs>
              <g v-for="v in [40,60,80,100]" :key="`yg${v}`">
                <line :x1="CPL" :y1="sy(v)" :x2="CPL+CW" :y2="sy(v)" stroke="#f0f0f0" stroke-width="1"/>
                <text x="0" :y="sy(v)+3.5" font-size="7" fill="#c0c0c0" font-family="sans-serif">{{ v }}</text>
              </g>
              <line v-if="!linePoints.length"
                :x1="CPL" :y1="sy(65)" :x2="CPL+CW" :y2="sy(65)"
                stroke="#e5e7eb" stroke-width="1" stroke-dasharray="4 3"/>
              <path v-if="linePoints.length>=2" :d="areaD" fill="url(#areaGrad)"/>
              <polyline v-if="linePoints.length>=2"
                :points="linePoints.map(p=>`${p.x},${p.y}`).join(' ')"
                fill="none" stroke="#3b82f6" stroke-width="2"
                stroke-linejoin="round" stroke-linecap="round"/>
              <circle v-for="(p,i) in linePoints" :key="`lp${i}`"
                :cx="p.x" :cy="p.y" r="3" fill="white" stroke="#3b82f6" stroke-width="1.8"/>
              <template v-if="linePoints.length">
                <circle :cx="lastPt.x" :cy="lastPt.y" r="5" fill="#3b82f6"/>
                <rect :x="tooltipX-22" :y="lastPt.y-23" width="44" height="16" rx="3" fill="#1e3a5f"/>
                <text :x="tooltipX" :y="lastPt.y-12"
                  text-anchor="middle" font-size="7.5" fill="white" font-weight="700" font-family="sans-serif"
                >{{ lastPt.label }} {{ lastPt.score }}分</text>
              </template>
              <text v-for="p in xAxisLabels" :key="`xl${p.label}${p.x}`"
                :x="p.x" y="118"
                text-anchor="middle" font-size="7" fill="#c0c0c0" font-family="sans-serif"
              >{{ p.label }}</text>
            </svg>
          </div>

          <div class="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-gray-100">
            <div>
              <div class="text-[10px] text-gray-400">训练次数</div>
              <div class="text-base font-black text-gray-800 mt-0.5 leading-none">
                {{ profile.summary.total_sessions }}<span class="text-[10px] text-gray-400 ml-0.5">次</span>
              </div>
            </div>
            <div>
              <div class="text-[10px] text-gray-400">平均分</div>
              <div class="text-base font-black text-gray-800 mt-0.5 leading-none">
                {{ scoreDisplay }}<span class="text-[10px] text-gray-400 ml-0.5">分</span>
              </div>
            </div>
            <div>
              <div class="text-[10px] text-gray-400">提升幅度</div>
              <div :class="['text-base font-black mt-0.5 leading-none', scoreGrowthUp ? 'text-green-500' : 'text-red-500']">
                {{ scoreGrowthText }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ════════════════════════════════════════
           BLOCK 3  最近训练记录
      ════════════════════════════════════════ -->
      <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <div class="text-sm font-black text-gray-800 mb-3">最近训练记录</div>

        <template v-if="recentScenes.length">
          <!-- 时间轴 -->
          <div class="relative mb-2" style="height:14px">
            <div class="absolute top-[6px] left-0 right-0 h-px bg-blue-200"></div>
            <div class="grid" :style="`grid-template-columns: repeat(${recentScenes.length}, 1fr)`">
              <div v-for="(_,i) in recentScenes" :key="`dot${i}`"
                class="flex justify-center items-center relative z-10">
                <div class="w-3 h-3 rounded-full bg-white border-2 border-[#3b82f6]"></div>
              </div>
            </div>
          </div>

          <!-- 卡片 grid，列数与时间轴点数一致 -->
          <div class="grid gap-3"
               :style="`grid-template-columns: repeat(${recentScenes.length}, 1fr)`">
            <div v-for="(item,idx) in recentScenes" :key="`rc${idx}`"
              class="rounded-xl border border-gray-100 px-4 pt-3 pb-3 hover:border-blue-200 hover:shadow-sm transition-all cursor-pointer group"
            >
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-[10px] text-gray-400">{{ item.latest_at || '' }}</span>
                <span :class="[
                  'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold',
                  item.status === '已完成' ? 'bg-green-50 text-green-600 border border-green-100'
                  : item.status === '进行中' ? 'bg-blue-50 text-blue-600 border border-blue-100'
                  : 'bg-gray-100 text-gray-500'
                ]">{{ item.status || '待完成' }}</span>
              </div>
              <h4 class="text-[13px] font-black text-gray-800 leading-snug line-clamp-2">{{ item.label }}</h4>
              <p class="text-[11px] text-gray-400 mt-1 truncate">
                {{ item.scene_type || sceneSubLabel(item.label) }}
              </p>
              <div class="flex items-end gap-2 mt-2.5">
                <span class="text-[32px] font-black text-[#1e3a5f] leading-none">{{ fmt(item.average_score) }}</span>
                <div class="flex flex-col pb-0.5">
                  <span class="text-[10px] text-gray-400 leading-none">分</span>
                  <span v-if="item.score_delta != null"
                    :class="['text-xs font-black mt-1', (item.score_delta??0)>=0 ? 'text-green-500' : 'text-red-500']">
                    {{ (item.score_delta??0)>=0 ? '↑' : '↓' }}&nbsp;{{ Math.abs(item.score_delta??0) }}
                  </span>
                </div>
              </div>
              <div class="mt-2">
                <span class="text-[11px] font-bold text-[#1a56db] group-hover:underline cursor-pointer">查看详情 →</span>
              </div>
            </div>
          </div>
        </template>
        <p v-else class="text-sm text-gray-400 py-8 text-center">暂无可展示的训练记录。</p>

        <div class="mt-3 pt-3 border-t border-gray-100 text-right">
          <span class="text-[11px] font-bold text-[#1a56db] cursor-pointer hover:underline">查看更多训练记录 →</span>
        </div>
      </div>

      <!-- ════════════════════════════════════════
           BLOCK 4  问题画像 + AI 训练建议
      ════════════════════════════════════════ -->
      <div class="grid grid-cols-2 gap-4">

        <!-- 问题画像 -->
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <div class="text-sm font-black text-gray-800 mb-4">问题画像</div>
          <div class="grid grid-cols-3 gap-4">

            <!-- 高频问题 -->
            <div>
              <div class="flex items-center gap-1.5 mb-2.5">
                <span class="w-[18px] h-[18px] rounded-full bg-orange-100 flex items-center justify-center flex-shrink-0">
                  <van-icon name="fire-o" size="9" class="text-orange-500"/>
                </span>
                <span class="text-[11px] font-black text-gray-700">高频问题 TOP3</span>
              </div>
              <div v-if="profile.high_frequency_issues.length" class="space-y-2.5">
                <div v-for="(item,i) in profile.high_frequency_issues.slice(0,3)" :key="`hf${i}`" class="flex gap-2">
                  <span class="w-4 h-4 rounded-full bg-orange-100 text-orange-600 text-[9px] font-black flex items-center justify-center flex-shrink-0 mt-0.5">{{ i+1 }}</span>
                  <div class="min-w-0">
                    <div class="text-[12px] font-semibold text-gray-700 leading-snug">{{ item.label }}</div>
                    <div class="text-[10px] text-gray-400 mt-0.5">出现 {{ item.count }} 次</div>
                  </div>
                </div>
              </div>
              <p v-else class="text-xs text-gray-400">暂无高频问题</p>
            </div>

            <!-- 高风险问题 -->
            <div>
              <div class="flex items-center gap-1.5 mb-2.5">
                <span class="w-[18px] h-[18px] rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                  <van-icon name="warning-o" size="9" class="text-red-500"/>
                </span>
                <span class="text-[11px] font-black text-gray-700">高风险问题 TOP3</span>
              </div>
              <div v-if="profile.high_risk_issues.length" class="space-y-2.5">
                <div v-for="(item,i) in profile.high_risk_issues.slice(0,3)" :key="`hr${i}`" class="flex gap-2">
                  <span class="w-4 h-4 rounded-full bg-red-100 text-red-600 text-[9px] font-black flex items-center justify-center flex-shrink-0 mt-0.5">{{ i+1 }}</span>
                  <div class="min-w-0">
                    <div class="text-[12px] font-semibold text-gray-700 leading-snug">{{ item.label }}</div>
                    <div class="text-[10px] text-gray-400 mt-0.5">出现 {{ item.count }} 次</div>
                  </div>
                </div>
              </div>
              <p v-else class="text-xs text-gray-400">暂无高风险问题</p>
            </div>

            <!-- 顽固问题 -->
            <div>
              <div class="flex items-center gap-1.5 mb-2.5">
                <span class="w-[18px] h-[18px] rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                  <van-icon name="replay" size="9" class="text-purple-500"/>
                </span>
                <span class="text-[11px] font-black text-gray-700">顽固问题</span>
              </div>
              <div v-if="stubbornRepeatLabel" class="rounded-lg bg-purple-50 px-2.5 py-1.5 mb-2">
                <div class="text-[10px] text-purple-600 font-semibold">{{ stubbornRepeatLabel }}</div>
              </div>
              <div v-if="profile.stubborn_issues.length" class="space-y-2.5">
                <div v-for="(item,i) in profile.stubborn_issues.slice(0,2)" :key="`st${i}`" class="flex gap-2">
                  <span class="w-4 h-4 rounded-full bg-purple-100 text-purple-600 text-[9px] font-black flex items-center justify-center flex-shrink-0 mt-0.5">{{ i+1 }}</span>
                  <div class="min-w-0">
                    <div class="text-[12px] font-semibold text-gray-700 leading-snug">{{ item.label }}</div>
                    <div class="text-[10px] text-gray-400 mt-0.5">已连续出现 {{ item.count }} 次以上</div>
                  </div>
                </div>
                <div v-if="profile.stubborn_issues[2]" class="rounded-lg bg-purple-50 px-2.5 py-2">
                  <div class="text-[11px] text-purple-700 font-semibold">{{ profile.stubborn_issues[2].label }}</div>
                  <div class="text-[10px] text-purple-500 mt-0.5">已连续出现 {{ profile.stubborn_issues[2].count }} 次</div>
                </div>
              </div>
              <p v-else class="text-xs text-gray-400">近期没有反复出现的问题</p>
            </div>
          </div>

          <div class="mt-4 pt-3 border-t border-gray-100 text-right">
            <span class="text-[11px] font-bold text-[#1a56db] cursor-pointer hover:underline">查看更多问题 →</span>
          </div>
        </div>

        <!-- AI 训练建议 -->
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <div class="flex items-center justify-between mb-3">
            <div class="text-sm font-black text-gray-800">AI 训练建议</div>
            <button class="flex items-center gap-1 text-[11px] text-gray-400 hover:text-[#1a56db] transition-colors"
              @click="fetchProfile">
              <van-icon name="replay" size="12"/> 换一批
            </button>
          </div>

          <div v-if="suggestionCards.length" class="space-y-2.5">
            <div v-for="(card,idx) in suggestionCards" :key="`sug${idx}`"
              class="flex gap-3 rounded-xl border border-gray-100 p-3 hover:border-blue-100 hover:bg-blue-50/20 transition-all">
              <div :class="['w-[60px] h-[60px] rounded-xl flex-shrink-0 flex items-center justify-center overflow-hidden', card.coverBg]">
                <van-icon name="orders-o" size="22" class="text-white/50"/>
              </div>
              <div class="flex-1 min-w-0">
                <div class="mb-1">
                  <span :class="['inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold', card.tagClass]">
                    {{ card.tag }}
                  </span>
                </div>
                <div class="text-[13px] font-black text-gray-800 leading-snug truncate">{{ card.title }}</div>
                <div class="text-[11px] text-gray-400 mt-0.5 line-clamp-1">{{ card.subDesc }}</div>
                <div class="flex items-center gap-0.5 mt-1.5">
                  <van-icon v-for="s in 5" :key="s" name="star" size="11"
                    :class="s <= card.stars ? 'text-yellow-400' : 'text-gray-200'"/>
                  <span class="text-[10px] text-gray-400 ml-1.5">匹配度 {{ card.match }}%</span>
                </div>
              </div>
              <div class="flex items-center flex-shrink-0">
                <button class="rounded-lg border border-[#1a3a6e] bg-white px-3 py-1.5 text-[11px] font-bold text-[#1a3a6e] hover:bg-[#1a3a6e] hover:text-white transition-colors whitespace-nowrap"
                  @click="router.push('/student/hall')">去训练</button>
              </div>
            </div>
          </div>

          <div v-else class="space-y-2">
            <div v-for="(text,idx) in profile.suggestions.slice(0,3)" :key="`fb${idx}`"
              class="flex gap-3 rounded-xl border border-gray-100 p-3">
              <div class="w-6 h-6 rounded-lg bg-blue-50 flex items-center justify-center text-xs font-black text-[#1a56db] flex-shrink-0">{{ idx+1 }}</div>
              <p class="text-xs text-gray-600 leading-relaxed">{{ text }}</p>
            </div>
            <p v-if="!profile.suggestions.length" class="text-xs text-gray-400 py-4 text-center">
              建议会在积累更多训练记录后自动补充。
            </p>
          </div>

          <div class="mt-3 pt-3 border-t border-gray-100 text-right">
            <span class="text-[11px] font-bold text-[#1a56db] cursor-pointer hover:underline">查看更多建议 →</span>
          </div>
        </div>
      </div>

    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '../utils/request'

// ─── 类型 ─────────────────────────────────────────────────────
type SceneItem = {
  label: string; session_count: number; average_score: number | null
  status: string; latest_at?: string; scene_type?: string; score_delta?: number | null
}
type ProfileResponse = {
  student: { id: number; username: string }
  summary: {
    level: string; summary_text: string
    total_sessions: number; finished_sessions: number
    average_score: number | null
    stability_status: string; progress_status: string
    latest_training_at: string | null
  }
  dimensions: Array<{ key: string; label: string; score: number; trend: string }>
  scene_performance: SceneItem[]
  high_frequency_issues: Array<{ label: string; count: number }>
  high_risk_issues: Array<{ label: string; count: number }>
  stubborn_issues: Array<{ label: string; count: number }>
  trend_points: Array<{ session_id: number; score: number; created_at: string | null }>
  suggestions: string[]
}

// ─── 状态 ─────────────────────────────────────────────────────
const route = useRoute()
const router = useRouter()
const setMainScrollable = inject<(v: boolean) => void>('setMainScrollable')
const loading = ref(false)
const pageError = ref('')
const profile = ref<ProfileResponse | null>(null)

// ─── 工具 ─────────────────────────────────────────────────────
const studentId = computed(() => Number(route.params.id || 0))
const studentCode = computed(() => `STU${String(studentId.value || 0).padStart(5, '0')}`)

const goBackToStudents = () => {
  if (window.history.length > 1) {
    router.back()
    return
  }
  router.push('/admin/students')
}

function fmt(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '--'
  return String(Math.round(Number(v)))
}
function norm(v: number | null | undefined): number {
  const n = Number(v || 0)
  return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : 0
}
function fmtDateShort(v: string | null | undefined): string {
  if (!v) return '--'
  const d = new Date(v)
  if (isNaN(d.getTime())) return '--'
  return `${d.getMonth() + 1}/${d.getDate()}`
}
function isValid(v: unknown): v is ProfileResponse {
  const o = v as any
  return Boolean(o && typeof o === 'object' && o.student && o.summary &&
    Array.isArray(o.dimensions) && Array.isArray(o.scene_performance) &&
    Array.isArray(o.high_frequency_issues) && Array.isArray(o.high_risk_issues) &&
    Array.isArray(o.stubborn_issues) && Array.isArray(o.trend_points) && Array.isArray(o.suggestions))
}
function sceneSubLabel(title: string): string {
  if (title.includes('醉驾')) return '现场控制与询问'
  if (title.includes('纠纷')) return '警情与风险初筛'
  if (title.includes('诈骗')) return '信息核实与劝阻'
  if (title.includes('交通')) return '事故认定与沟通'
  return '训练场景'
}

// ─── 学员基础信息 ─────────────────────────────────────────────
const scoreDisplay = computed(() => fmt(profile.value?.summary?.average_score))
const studentInitials = computed(() => String(profile.value?.student?.username || 'ST').trim().slice(0, 2).toUpperCase())
const primarySceneLabel = computed(() => profile.value?.scene_performance?.[0]?.label || '综合训练单元')

const sortedDims = computed(() =>
  [...(profile.value?.dimensions || [])].sort((a, b) => Number(b.score||0) - Number(a.score||0)))
const strengths = computed(() => sortedDims.value.slice(0, 2))
const weaknesses = computed(() => [...sortedDims.value].reverse().slice(0, 2))

const traitTags = computed(() => {
  const s = [strengths.value[0]?.label, profile.value?.summary?.stability_status, profile.value?.summary?.progress_status]
    .filter(Boolean) as string[]
  return s.length ? s.slice(0, 3) : ['持续积累中']
})
const topPct = computed(() => {
  const sc = Number(profile.value?.summary?.average_score || 0)
  if (sc >= 85) return 'Top 10%'; if (sc >= 75) return 'Top 15%'
  if (sc >= 65) return 'Top 30%'; return '持续提升中'
})
const summaryStats = computed(() => [
  { label:'累计训练', value:`${profile.value?.summary?.total_sessions||0} 次`,   icon:'orders-o',        iconBg:'bg-blue-50',   iconColor:'text-blue-500',   valColor:'text-gray-800' },
  { label:'完成训练', value:`${profile.value?.summary?.finished_sessions||0} 次`, icon:'passed',          iconBg:'bg-green-50',  iconColor:'text-green-500',  valColor:'text-gray-800' },
  { label:'平均分',   value:`${scoreDisplay.value} 分`,                            icon:'chart-trending-o',iconBg:'bg-orange-50', iconColor:'text-orange-400', valColor:'text-gray-800' },
  { label:'排名',     value:topPct.value,                                          icon:'award-o',         iconBg:'bg-purple-50', iconColor:'text-purple-500', valColor:'text-purple-600' },
  { label:'稳定性',   value:profile.value?.summary?.stability_status||'--',        icon:'balance-o',       iconBg:'bg-teal-50',   iconColor:'text-teal-500',   valColor:'text-gray-800' },
  { label:'成长速度', value:profile.value?.summary?.progress_status||'--',         icon:'fire-o',          iconBg:'bg-red-50',    iconColor:'text-red-400',    valColor:'text-green-600' },
])

// ─── 雷达图 ───────────────────────────────────────────────────
const abilityRows = computed(() => {
  const items = profile.value?.dimensions || []
  if (items.length) return items
  return [
    { key:'comm', label:'沟通表达', score:0, trend:'' },
    { key:'proc', label:'流程规范', score:0, trend:'' },
    { key:'risk', label:'风险判断', score:0, trend:'' },
    { key:'emo',  label:'情绪控制', score:0, trend:'' },
    { key:'info', label:'信息获取', score:0, trend:'' },
  ]
})
const RCX=100, RCY=100, RR=62
function rPt(i:number,n:number,r:number){ const a=(Math.PI*2*i/n)-Math.PI/2; return {x:RCX+r*Math.cos(a),y:RCY+r*Math.sin(a)} }
function radarBgPts(pct:number):string {
  const n=abilityRows.value.length||5
  return Array.from({length:n},(_,i)=>rPt(i,n,(pct/100)*RR)).map(p=>`${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
}
const radarAxisPts = computed(()=>{ const n=abilityRows.value.length||5; return Array.from({length:n},(_,i)=>rPt(i,n,RR)) })
const radarDotList = computed(()=> abilityRows.value.map((item,i)=>rPt(i,abilityRows.value.length,(norm(item.score)/100)*RR)))
const radarDataPts = computed(()=> radarDotList.value.map(p=>`${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '))
const radarAvgPts  = computed(()=>{ const n=abilityRows.value.length||5; return Array.from({length:n},(_,i)=>rPt(i,n,(65/100)*RR)).map(p=>`${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') })
const radarLabelPts= computed(()=>{ const n=abilityRows.value.length; return Array.from({length:n},(_,i)=>rPt(i,n,RR+24)) })

// ─── 折线图 ───────────────────────────────────────────────────
// viewBox: 0 0 400 120
const CPL=28, CW=364, CPT=8, CCH=94
const YMIN=40, YMAX=100
function sy(v:number):number { const c=Math.max(YMIN,Math.min(YMAX,v)); return CPT+CCH-((c-YMIN)/(YMAX-YMIN))*CCH }
function sx(i:number,total:number):number { if(total<=1) return CPL+CW/2; return CPL+(i/(total-1))*CW }

const trendPts = computed(()=>
  (profile.value?.trend_points||[]).map(item=>({
    key:item.session_id, score:norm(item.score), label:fmtDateShort(item.created_at)
  })).filter(item=>Number.isFinite(item.score))
)
const linePoints = computed(()=>{
  const pts=trendPts.value; if(!pts.length) return []
  return pts.map((pt,i)=>({x:sx(i,pts.length), y:sy(pt.score), score:pt.score, label:pt.label}))
})
const areaD = computed(()=>{
  const ps=linePoints.value; if(ps.length<2) return ''
  const bY=CPT+CCH
  const line=ps.map((p,i)=>`${i===0?'M':'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  return `${line} L${ps[ps.length-1].x.toFixed(1)},${bY} L${ps[0].x.toFixed(1)},${bY} Z`
})
const lastPt = computed(()=>linePoints.value[linePoints.value.length-1] ?? {x:0,y:0,score:0,label:''})
const tooltipX = computed(()=>{ const lx=lastPt.value.x; return lx+22>CPL+CW?lx-22:lx })
const xAxisLabels = computed(()=>{
  const ps=linePoints.value; if(!ps.length) return []
  const step=Math.max(1,Math.floor(ps.length/5))
  return ps.filter((_,i)=>i===0||i===ps.length-1||i%step===0)
})
const scoreDelta = computed(()=>{
  const pts=trendPts.value; if(pts.length<2) return 0
  return pts[pts.length-1].score-pts[pts.length-2].score
})
const scoreGrowthText = computed(()=>{
  const pts=trendPts.value; if(pts.length<2) return '--'
  const first=pts[0].score, last=pts[pts.length-1].score
  if(!first) return '--'
  return `${((last-first)/first*100)>=0?'+':''}${((last-first)/first*100).toFixed(0)}%`
})
const scoreGrowthUp = computed(()=>scoreGrowthText.value==='--'||scoreGrowthText.value.startsWith('+'))

// ─── 最近训练记录 ─────────────────────────────────────────────
const recentScenes = computed(()=>(profile.value?.scene_performance||[]).slice(0,4))

// ─── 问题画像 ─────────────────────────────────────────────────
const stubbornRepeatLabel = computed(()=>{
  const issues=profile.value?.stubborn_issues||[]; if(!issues.length) return ''
  const max=issues.reduce((a,b)=>a.count>b.count?a:b)
  return `连续出现 ${max.count} 次及以上`
})

// ─── AI 建议 ──────────────────────────────────────────────────
const TAG_STYLES = [
  { tag:'推荐重点训练', tagClass:'bg-red-50 text-red-500 border border-red-100',       coverBg:'bg-gradient-to-br from-[#1e3a5f] to-[#1a56db]' },
  { tag:'推荐加强训练', tagClass:'bg-orange-50 text-orange-500 border border-orange-100', coverBg:'bg-gradient-to-br from-[#1e3a5f] to-[#2563eb]' },
  { tag:'推荐巩固训练', tagClass:'bg-blue-50 text-blue-600 border border-blue-100',    coverBg:'bg-gradient-to-br from-[#1e3a5f] to-[#3b82f6]' },
]
const suggestionCards = computed(()=>{
  const sugs=profile.value?.suggestions||[]; const scenes=profile.value?.scene_performance||[]
  if(!sugs.length) return []
  return sugs.slice(0,3).map((text,i)=>{
    const scene=scenes[i]; const match=92-i*7; const stars=match>=90?5:match>=80?4:3
    return { title:scene?.label||`训练建议 ${i+1}`, subDesc:text, stars, match, ...TAG_STYLES[i%TAG_STYLES.length] }
  })
})

// ─── 数据加载 ─────────────────────────────────────────────────
const fetchProfile = async () => {
  if (!studentId.value) { pageError.value='缺少学员编号。'; profile.value=null; return }
  loading.value=true; pageError.value=''; profile.value=null
  try {
    const result = await request.get(`/auth/students/${studentId.value}/profile`, { timeout:15000, _skipErrorToast:true } as any)
    if (!isValid(result)) { pageError.value='画像数据暂未准备完成，请稍后再试。'; return }
    profile.value=result
  } catch { pageError.value='画像加载失败，请确认后端服务已启动后再试。' }
  finally { loading.value=false }
}

onMounted(()=>{ setMainScrollable?.(false); fetchProfile() })
onUnmounted(()=>{ setMainScrollable?.(false) })
watch(()=>route.params.id, fetchProfile)
</script>

<style scoped>
.student-profile-page {
  min-height: 100%;
  overflow: visible;
  padding-right: 4px;
}

.student-profile-backbar {
  position: sticky;
  top: 0;
  z-index: 8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.96);
  padding: 10px 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(8px);
}

.student-profile-backbar span {
  color: #334155;
  font-size: 14px;
  font-weight: 800;
}
</style>
