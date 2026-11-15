# -*- coding: utf-8 -*-
"""新闻筛选口径：只保留「发射类」与「国际规则/监管类」。

发射类：谁（国家/机构/公司）在何时用哪型火箭发射了什么、多少颗、什么任务。
规则类：航天发射、轨道、频率相关的国际规则、条约或监管政策出台。
其余（融资估值、周年庆、听证人事、官员表态、产品宣传等）一律过滤。
"""
import re

# 发射行为的动词 / 词组。只用明确的「已发生/正在发生」表述，
# 避免把 "launch vehicle"（名词修饰）和 "developing a launch vehicle"（战略）算成发射事件。
_LAUNCH_VERB = re.compile(
    r"(?i)\b(launches|launched|launching|liftoff|lift[- ]off|lofts|lofted|"
    r"deploys|deployed|sent into orbit|sends? .{0,30} into orbit|"
    r"place[sd]? .{0,20} (?:in|into) orbit|put[s]? .{0,20} into orbit|orbited|"
    r"(?:maiden|inaugural|first|second|third|final|next) launch(?:es|ed)?|"
    r"launch(?:es|ed)? (?:a|an|the|its|their|two|three|four|\d+|new|another|more)|"
    r"launch of|flight[- ]test(?:s|ed)?|static fire|rolled out to the pad)\b"
)

# 必须是航天硬件，避免「公司发布新产品」被误判为发射
_HARDWARE = re.compile(
    r"(?i)\b(rocket|booster|satellites?|spacecraft|payloads?|space station|"
    r"spacelab|probe|lander|rover|upper stage|fairing|constellation|orbiter|"
    r"telescope|capsule|module|launch vehicle|block \d|"
    r"long march|falcon \d|falcon heavy|starship|soyuz|ariane|electron|vega|"
    r"atlas|delta|h3|h-3|kuaizhou|ceres|new glenn|neutron|terran|angara|"
    r"proton|zenit|antares|minotaur|pegasus|hyperbola|gravity-\d|"
    r"zhuque|tianlong|kuiper|starlink|oneweb|qianfan|guowang)\b"
)

_LAUNCH_CN = re.compile(r"(发射|点火升空|运载火箭|一箭|卫星入轨|飞船入轨|载荷入轨)")

# 国际规则 / 监管政策
_POLICY = re.compile(
    r"(?i)\b(spectrum|radio frequency|frequency allocation|frequency coordination|"
    r"\bITU\b|international telecommunication union|\bWRC\b|wrc-\d+|"
    r"\bFCC\b|approv(?:e|es|ed|al)|authoriz(?:e|es|ed|ation)|certification|"
    r"orbital debris|space traffic|space sustainability|space safety|"
    r"rulemaking|rule[- ]mak\w+|regulat\w+|regulator|regulatory|"
    r"licen[cs]\w+|moratorium|treaty|accord|binding rules|"
    r"international (?:rules?|standards?|guidelines?|framework|agreement)|"
    r"outer space treaty|space law|coordination (?:mechanism|framework)|"
    r"orbit(?:al)? (?:slots?|allocation|resources?))\b"
)
_POLICY_CN = re.compile(r"(国际规则|规则|监管|政策|频谱|频率|轨道资源|国际电信联盟|条约|协定|协调机制|立法)")

_SPACE_CONTEXT = re.compile(
    r"(?i)\b(space|satellite|orbit|orbital|launch|rocket|spectrum|frequency|"
    r"constellation|telecom|remote sensing|spacecraft)\b"
)

# 明确不属于本 App 目的的主题
_EXCLUDE_TITLE = re.compile(
    r"(?i)\b(funding|fundraise|fundraising|raises? \$|raised \$|valuation|"
    r"series [a-e]\b|\bIPO\b|\bSPAC\b|acquisition|acquires?|merger|merges?|buyout|"
    r"stake|shareholders?|investors?|earnings|revenue|profit|backlog|"
    r"anniversary|celebrat\w+|appoints?|appointed|names? (?:new )?(?:ceo|chief)|"
    r"\bCEO\b|chief executive|executive|hires?|hiring|layoffs?|workforce|"
    r"hearing|confirmation|nominee|senate|congress\w*|lawmakers?|testimony|"
    r"remarks|speech|interview|opinion|op-ed|commentary|podcast|webinar|"
    r"awards?|unveils?|unveiling|product|marketing|campaign|advertis\w+|"
    r"\bstock\b|\bshares\b|partnership|memorandum|\bMoU\b|summit|conference|"
    r"expo|trade show|factory|manufacturing plant|opens? (?:new )?office|"
    r"obituary|passes away|dies at)\b"
    r"|(融资|估值|上市|募资|收购|并购|股权|财报|营收|利润|周年|庆典|"
    r"人事|任免|任命|听证|参议院|众议院|表态|讲话|致辞|会见|座谈|签约|"
    r"发布会|产品|宣传|广告|论坛|峰会|展会|工厂|生产线)"
)

EXCLUDE_REASON = {
    "funding": "融资/估值", "business": "企业经营", "politics": "政治/人事",
    "product": "产品宣传", "event": "活动/庆典", "none": "与发射或规则无关",
}

# 评论、观点、访谈类：不是在报道某次发射或某条规则
_OPINION = re.compile(
    r"(?i)^(how|why|what|can|will|should|is|are|could|would|does|when)\b|"
    r"\b(opinion|commentary|editorial|analysis|interview|podcast|webinar|"
    r"perspective|viewpoint|op-ed)\b"
)


def _hit(pattern, text):
    m = pattern.search(text)
    return m.group(0) if m else None


def judge(title, summary=""):
    """返回 (keep, category, reason)。

    category: "launch" / "policy" / ""。
    keep=False 时 reason 为可复核的中文说明。
    """
    title = title or ""
    body = summary or ""
    text = title + " " + body

    if _OPINION.search(title) or title.rstrip().endswith('?'):
        return False, "", "评论/观点/访谈类，不是发射或规则报道"

    launch_title = bool(_LAUNCH_VERB.search(title) and _HARDWARE.search(title)) or bool(_LAUNCH_CN.search(title))
    policy_title = (bool(_POLICY.search(title)) and bool(_SPACE_CONTEXT.search(title))) or bool(_POLICY_CN.search(title))
    launch_body = bool(_LAUNCH_VERB.search(text) and _HARDWARE.search(text)) or bool(_LAUNCH_CN.search(text))
    policy_body = bool(_POLICY.search(text)) and bool(_SPACE_CONTEXT.search(text))

    # 标题就是发射/规则报道：优先保留，除非标题同时是明显的企业/政治新闻
    if launch_title or policy_title:
        bad = _EXCLUDE_TITLE.search(title)
        if bad and not (launch_title and _HARDWARE.search(title) and _LAUNCH_VERB.search(title)):
            return False, "", "标题含「%s」，非发射/规则报道" % bad.group(0)
        return True, ("launch" if launch_title else "policy"), ""

    bad = _EXCLUDE_TITLE.search(title)
    if bad:
        return False, "", "标题含「%s」" % bad.group(0)

    if launch_body:
        return True, "launch", ""
    if policy_body:
        return True, "policy", ""
    return False, "", "无发射或国际规则信号"
