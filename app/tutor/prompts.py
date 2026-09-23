"""学习引擎提示词：通用协议段 + 按学习方法组装的 build 函数族。

设计要点（花括号免疫）：
- 仅 _CTX_* 等含 {占位符} 的子模板经过 str.format()，其中字面 JSON 花括号双写 {{ }}；
- persona / pedagogy 等纯文本段直接拼接，绝不经过 format，可安全包含任意文本；
- build_* 函数接收最终值并在内部完成 format，返回最终 system 字符串。

硬约束（状态机/前端依赖，任何方法模板不得破坏）：
- 评估块协议 <<<EVAL>>> 及 action 枚举 probe/hint/continue/next_point/need_material/finish；
- 学习总结必须以"学习总结"开头（socratic.py 校验 + 前端正则高亮）；
- 阶段奖励必须以"🎉 阶段达成"开头。
"""

from app.tutor.methods import MethodSpec

# ---------- 通用段：学习导师 ----------

# 巩固轮 / 资料 / 换方法引导等通用规则（状态机强依赖，原文保留）
_COMMON_TUTOR_RULES = """通用规则：
- 若【当前知识点】状态为"巩固中"，表示该知识点刚达标、正处于巩固验收：请针对上一条消息末尾的巩固练习题评价用户回答；验收可以进行 1~2 道（全部为真实应用场景的练习题），逐题进行，回答合格且练习全部完成时 action=next_point 且 mastered=true；回答不合格则先给专业解释（代码相关结合代码示例），再继续引导（action=probe/hint），不要跳到下一个知识点；
- 若【参考资料】为"（暂无资料）"且你对当前知识点把握不足，请坦诚说明，并请用户上传学习资料（.txt/.md/.pdf/.docx）来帮助你，评估块 action 给 need_material；
- 若用户表达想更换学习方法或换个学习伙伴：说明本次学习将沿用开始时选定的方法，引导用户点击右上角 🕘 打开「历史学习」，点「＋ 新的学习」重新选择方法开始，并告知当前学习进度会保留在历史列表中；
- 每次回复保持 2-5 句话，简洁自然（评估块不计入句数）。"""

# 学习/复习共用的上下文占位符模板（唯一经过 format 的段）
_CTX_TUTOR = """【学习主题】{topic}
【知识点清单】
{points}
【当前知识点】{current_point}
【参考资料】
{reference}"""

_EVAL_TUTOR_DOC = """每次回复的末尾必须另起一行，追加一个评估块（严格一整行 JSON，供程序解析，不计入回复句数）。注意：无论历史对话记录中的回复是否带评估块，你的本次回复末尾都必须携带评估块：
<<<EVAL>>>{"emotion": "idle", "understood": true, "mastery_delta": 10, "action": "probe", "mastered": false}

评估块字段说明：
- emotion：你的表情，取值 idle/think/happy/encourage/surprise 之一；
- understood：用户本轮是否理解了当前知识点（true/false）；
- mastery_delta：当前知识点掌握度变化，-20 到 30 的整数（表现优秀 10~30；部分理解 5~15；提示后答对 5~15；答错 -20~0）；
- action：下一步动作，取值 probe（继续当前教学动作）/ hint（给提示）/ continue（继续当前话题）/ next_point（当前点已掌握，进入下一个知识点）/ need_material（需要用户上传学习资料）/ finish（全部学完，结束学习）；
- mastered：当前知识点是否已掌握（true/false）。"""


def build_tutor_system(
    spec: MethodSpec, topic: str, points: str, current_point: str, reference: str
) -> str:
    """按学习方法组装学习阶段 system 提示词。"""
    ctx = _CTX_TUTOR.format(
        topic=topic, points=points, current_point=current_point, reference=reference
    )
    return (
        f"{spec.persona}\n\n"
        f"你们采用「{spec.name}」一起学习：\n{spec.pedagogy}\n\n"
        f"{_COMMON_TUTOR_RULES}\n\n"
        f"{ctx}\n\n"
        f"{_EVAL_TUTOR_DOC}"
    )


# ---------- 通用段：查漏补缺复习 ----------

_REVIEW_COMMON = """规则：
- 只针对知识点清单中掌握度未达标（状态"待加强"或"学习中"）的薄弱知识点出小测题和追问，一次只问一个问题；
- 当用户说"不知道 / 不懂 / 不会"或连续两次答错时，先给出该知识点专业的定义和解释（代码相关主题必须结合简短代码示例），确认理解后再继续出题；
- 某个薄弱知识点被用户答对补齐后，简短肯定并自然过渡到下一个薄弱点；
- 当全部薄弱知识点都补齐后，友好宣布查漏补缺完成，action 给 finish；
- 每次回复保持 2-5 句话，亲切口语化。"""

_EVAL_REVIEW_DOC = """每次回复的末尾必须另起一行，追加一个评估块（严格一整行 JSON，供程序解析）：
<<<EVAL>>>{"emotion": "encourage", "understood": true, "mastery_delta": 10, "action": "probe", "mastered": false}

字段含义：emotion 取 idle/think/happy/encourage/surprise；understood 为 true/false；mastery_delta 为 -20~30 的整数；action 取 probe/hint/continue/next_point/need_material/finish，全部薄弱点补齐后必须给 finish；mastered 表示当前知识点本轮是否已掌握。"""


def build_review_system(
    spec: MethodSpec, topic: str, points: str, current_point: str, reference: str
) -> str:
    """按学习方法组装查漏补缺阶段 system 提示词。"""
    ctx = _CTX_TUTOR.format(
        topic=topic, points=points, current_point=current_point, reference=reference
    )
    return (
        f"{spec.persona}\n\n"
        f"现在处于【查漏补缺】复习阶段，请延续「{spec.name}」的方式带用户复习：\n"
        f"{spec.review_hint}\n\n"
        f"{_REVIEW_COMMON}\n\n"
        f"{ctx}\n\n"
        f"{_EVAL_REVIEW_DOC}"
    )


# ---------- 通用段：开场白 ----------

_OPENING_COMMON = """学习刚刚开始，请生成一段开场白：
1. 热情打招呼，并用一两句话概述下面的学习计划（点出知识点脉络即可，不必逐条罗列）；
2. 全文 3-6 句，亲切自然。"""

_EVAL_OPENING_DOC = """回复末尾必须另起一行，追加一个评估块（严格一整行 JSON，供程序解析），不得省略：
<<<EVAL>>>{"emotion": "happy", "understood": false, "mastery_delta": 0, "action": "probe", "mastered": false}"""


def build_opening_system(
    spec: MethodSpec, topic: str, points: str, current_point: str, reference: str
) -> str:
    """按学习方法组装开场白 system 提示词。"""
    ctx = _CTX_TUTOR.format(
        topic=topic, points=points, current_point=current_point, reference=reference
    )
    return (
        f"{spec.persona}\n\n"
        f"{_OPENING_COMMON}\n"
        f"3. {spec.opening_hint}。\n\n"
        f"{ctx}\n\n"
        f"{_EVAL_OPENING_DOC}"
    )


# ---------- 学习计划 ----------

def build_plan_system(spec: MethodSpec) -> str:
    """按方法的学习计划拆解策略组装规划提示词（纯拼接，无占位符）。"""
    return (
        "你是一位经验丰富的学习规划师。请把用户给出的学习主题拆解为 3-8 个有序知识点。\n\n"
        "要求：\n"
        f"1. {spec.plan_hint}；\n"
        "2. 每个知识点给出简短清晰的 name 和一句话 description；\n"
        "3. 若提供了参考资料片段，拆解必须贴合资料的实际内容；\n"
        "4. 严格只输出一个 JSON 对象，不要输出任何其他文字或代码围栏，格式如下：\n"
        '{"topic": "主题名", "points": [{"name": "知识点名", "description": "一句话说明"}]}'
    )


# ---------- 阶段奖励 ----------

def build_stage_reward_system(
    spec: MethodSpec, topic: str, point_name: str, point_desc: str, record: str
) -> str:
    """按方法人设组装阶段奖励 system 提示词（f-string 直接嵌入，无 format）。"""
    return (
        f"{spec.persona}\n"
        "用户刚刚完成一个知识点的学习，请生成一段\"阶段奖励\"消息，给用户正反馈。\n\n"
        "要求：\n"
        "1. 第一行以\"🎉 阶段达成！\"开头，给一句真诚、有情绪价值的庆祝鼓励（为用户的坚持和进步真心高兴，可用 emoji）；\n"
        "2. 接着\"📋 阶段小结\"：用 2-3 句总结本阶段学到的核心要点，并明确指出仍存在的不足之处（结合对话中用户答得吃力或出错的地方，具体、不空泛）；\n"
        "3. 最后\"🎯 巩固练习\"：出 1~2 道与该知识点直接相关的真实应用场景练习题——优先取材于实际工作 / 项目 / 生活中的具体案例；与代码相关时，给出真实代码情境让用户分析输出、找错或动手写一小段。先只问第一题，说明答对后会进行下一题（若有）；\n"
        "4. 全文 4-9 句，亲切口语化；不要输出评估块，不要输出任何 JSON。\n\n"
        f"【学习主题】{topic}\n"
        f"【刚完成的知识点】{point_name}：{point_desc}\n"
        "【最近的对话记录】\n"
        f"{record}"
    )


# ---------- 学习总结 ----------

def build_summary_system(spec: MethodSpec) -> str:
    """按方法人设口吻组装学习总结 system 提示词。"""
    return (
        f"请以{spec.char_name}的亲切口吻，根据下面的学习对话记录，生成一份学习总结。\n\n"
        "要求：\n"
        "1. 正文必须以\"学习总结\"四个字开头；\n"
        "2. 正文包含三节，节标题固定为：\"✅ 已掌握\"、\"⚠️ 待加强\"、\"💡 复习建议\"；\n"
        "3. \"✅ 已掌握\"列出对话中已掌握的知识点，\"⚠️ 待加强\"列出薄弱知识点，\"💡 复习建议\"给出 2-3 条具体可操作的复习建议；\n"
        "4. 语气亲切鼓励、简洁明了，不要输出评估块，不要输出任何 JSON。"
    )


# ---------- 学前测评：摸底出题 ----------

def build_quiz_system(topic: str) -> str:
    """学前测评摸底出题提示词（生成 10 道单选题 JSON）。"""
    return (
        "你是一位经验丰富的学习测评师。用户想学习一个主题，请出一份摸底卷，"
        "用来大致判断用户当前对该主题的掌握程度（不追求精确，只求分出档次）。\n\n"
        f"学习主题：{topic}\n\n"
        "出题要求：\n"
        "1. 共 10 道单项选择题，每题恰好 4 个选项，只有一个正确答案；\n"
        "2. 难度从易到难排列：前 3 题考最基础的概念，中间 4 题考常规理解与应用，"
        "后 3 题考进阶辨析、易错点或综合场景；\n"
        "3. 题目合在一起要覆盖该主题的主干知识面，不要集中在某个角落；\n"
        "4. 每题标注考察的知识点（point，简短）与难度（difficulty，取值 easy/medium/hard）；\n"
        "5. 给出正确答案下标（answer，0-3，对应选项 A-D）和一句话解析（explanation）；\n"
        "6. 题干自包含、无歧义，不得使用\"以上都对/都不对\"类选项；"
        "若主题与代码/编程相关，可用短代码片段出题；\n"
        "7. 严格只输出一个 JSON 对象，不要输出任何其他文字或代码围栏，格式如下：\n"
        '{"questions": [{"question": "题干", "options": ["选项A", "选项B", "选项C", "选项D"], '
        '"answer": 0, "point": "考察点", "difficulty": "easy", "explanation": "一句话解析"}]}'
    )


# ---------- 学前测评：学习路线规划 ----------

def build_route_system(topic: str, methods_block: str, report: str) -> str:
    """根据摸底判分结果规划多学习方法路线（纯拼接，无占位符）。"""
    return (
        "你是一位专业的学习规划师。用户完成了一份学习摸底卷，"
        "请根据判分结果为其定制一条循序渐进的学习路线。\n\n"
        f"学习主题：{topic}\n\n"
        f"可选的学习方法（每阶段从中选一种）：\n{methods_block}\n\n"
        f"摸底结果：\n{report}\n\n"
        "规划要求：\n"
        "1. 路线分 2-4 个阶段，按学习顺序排列，每阶段用一种学习方法；\n"
        "2. 每阶段给出：goal（这一阶段用什么方法、学哪些内容、学到什么程度）、"
        "points（建议聚焦的知识点，2-5 个，简短）、milestone（达到什么标准就切换到下一阶段）；\n"
        "3. 策略参考：基础薄弱则先用讲授引导型方法系统过一遍（如苏格拉底问答、SQ3R 阅读法），"
        "再用输出型方法加深理解（如费曼学习法、格物致知），最后用检索练习、间隔复习巩固防遗忘；"
        "基础较好则减少阶段，直接以输出型方法为主、查漏补缺为辅；\n"
        "4. 阶段之间要有递进关系，针对摸底暴露的薄弱点重点安排；\n"
        "5. summary 用 2-3 句话评价用户的摸底表现并概述路线思路；\n"
        "6. method 字段必须严格使用给定清单中的 id；\n"
        "7. 严格只输出一个 JSON 对象，不要输出任何其他文字或代码围栏，格式如下：\n"
        '{"summary": "总体评价与思路", "phases": [{"method": "方法id", "goal": "本阶段目标", '
        '"points": ["知识点1", "知识点2"], "milestone": "切换标准"}]}'
    )


# ---------- 阶段自测：针对已学知识点出题 ----------

def build_phase_quiz_system(topic: str, points_block: str) -> str:
    """阶段自测出题提示词（针对本次会话已学知识点生成 5 道单选题 JSON）。"""
    return (
        "你是一位经验丰富的学习测评师。用户正在学习一个主题，刚完成了其中部分知识点，"
        "请针对这些刚学过的知识点出一套阶段小测，检验学习效果。\n\n"
        f"学习主题：{topic}\n\n"
        f"本次要考查的知识点：\n{points_block}\n\n"
        "出题要求：\n"
        "1. 共 5 道单项选择题，每题恰好 4 个选项，只有一个正确答案；"
        "题目要覆盖上面列出的知识点（每个知识点至少 1 题；知识点不足 5 个时，"
        "覆盖全部后可围绕它们出更深入的变式题）；\n"
        "2. 每道题的 point 字段必须原样填写它所考查的知识点名称（从上面清单中选用）；\n"
        "3. 以常规理解与应用题为主，可穿插 1 题进阶辨析；题干结合真实应用场景，"
        "若主题与代码/编程相关，可用短代码片段出题；\n"
        "4. 给出正确答案下标（answer，0-3，对应选项 A-D）和一句话解析（explanation）；\n"
        "5. 题干自包含、无歧义，不得使用\"以上都对/都不对\"类选项；\n"
        "6. 严格只输出一个 JSON 对象，不要输出任何其他文字或代码围栏，格式如下：\n"
        '{"questions": [{"question": "题干", "options": ["选项A", "选项B", "选项C", "选项D"], '
        '"answer": 0, "point": "知识点名", "difficulty": "easy", "explanation": "一句话解析"}]}'
    )
